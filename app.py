import os
import cv2 
import numpy as np 
import threading
import uuid
from typing import Dict
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from eye_tracker import EyeTracker
from audio_tracker import AudioTracker
from config import APP_CONFIG

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# initialize web service 
app = FastAPI(title="Anti-Cheating AI Proctoring Service")

# connect frontend with backend hosting
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# initialize engine 
eye_tracker = EyeTracker(config=APP_CONFIG)
audio_tracker = AudioTracker(config=APP_CONFIG)
DB_DIR = "./database"
embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = ChatOllama(model="llama3.2:1b", temperature=0.2)

# =======================================================
# LOCAL RAG PIPELINE
# =======================================================

# load vector database 
vectore_store = Chroma(
    persist_directory=DB_DIR, 
    embedding_function=embeddings
)
retriever = vectore_store.as_retriever(search_kwargs={"k": 2})  # retrieve top 2 similar answers

# Format helper to clean up database outputs for the prompt
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# tell LLM how to act using our system guidelines 
# context: the place where LangChain paste the matching paragraph from ChromaDB 

# --- PIPELINE 1: The Live Chatbot Brain ---
chatbot_instruction = (
    "You are a helpful AI Proctor Assistant. Your job is to answer structural, operational, "
    "and rule questions about the exam using ONLY the context provided below.\n"
    "Be direct, polite, and brief. If the answer isn't in the context, say: "
    "'I am sorry, I can only answer questions regarding exam rules and schedules.'\n\n"
    "Context:\n{context}"
)
chatbot_prompt = ChatPromptTemplate.from_messages([
    ("system", chatbot_instruction),
    ("human", "{input}")
])

chatbot_chain = (
    {"context": retriever | format_docs, "input": RunnablePassthrough()}
    | chatbot_prompt
    | llm
    | StrOutputParser()
)

# --- PIPELINE 2: The Automated Evaluator Brain ---
evaluator_instruction = (
    "You are an expert Technical Interview Grading System. Your exclusive task is to evaluate "
    "the candidate's transcript against the question rubrics found in the context documents.\n"
    "Provide a detailed breakdown of their score (1-5 scale) based on the criteria profiles. "
    "Highlight specific missing target concepts or explicit negative indicators.\n\n"
    "Context:\n{context}"
)
evaluator_prompt = ChatPromptTemplate.from_messages([
    ("system", evaluator_instruction),
    ("human", "{input}")
])
# Clean LCEL pipeline tailored specifically for grading reports
evaluator_chain = (
    {"context": retriever | format_docs, "input": RunnablePassthrough()}
    | evaluator_prompt
    | llm
    | StrOutputParser()
)

# =======================================================
# SCHEMAS
# =======================================================
class ChatRequest(BaseModel):
    user_message: str

class StartSessionRequest(BaseModel):
    candidate_name: str

# live session memory core
class InterviewSession: 
    def __init__(self, candidate_name):
        self.candidate_name = candidate_name
        self.gaze_flags = 0
        self.script_flags = 0
        self.audio_flags = 0 
        self.transcripts = []
        self.lock = threading.Lock()  # protects data when frames & audio arrive same time
    
    def to_dict(self): 
        with self.lock: 
            return {
                "candidate_name": self.candidate_name,
                "metrics": {
                    "gaze_looking_away_events": self.gaze_flags,
                    "gaze_reading_events": self.script_flags,
                    "ai_generated_speech_events": self.audio_flags,
                },
                "recent_transcripts": self.transcripts[-5:] # Last 5 text blocks
            }

# Global dict to remember active sessions on the server 
ACTIVE_SESSIONS: Dict[str, InterviewSession] = {}

# =======================================================
# SESSION CONTROL ENDPOINTS 
# =======================================================
@app.post("/api/session/start")
async def start_interview(payload: StartSessionRequest): 
    """Initializes a new tracking memory box on the server."""
    session_id = str(uuid.uuid4())[:8]
    ACTIVE_SESSIONS[session_id] = InterviewSession(candidate_name=payload.candidate_name)
    return {"session_id": session_id, 
            "status": "started"}

@app.get("/api/session/{session_id}/status")
async def get_live_status(session_id: str):
    """Frontend read from here to display flag numbers live."""
    if session_id not in ACTIVE_SESSIONS:
        raise HTTPException(status_code=404, detail="Session expired or not found")
    return ACTIVE_SESSIONS[session_id].to_dict()

# =======================================================
# ANALYZER ENDPOINTS 
# =======================================================
@app.post("/api/proctor/eye-tracker")
async def eye_analyzer(session_id: str, file: UploadFile = File(...)):
    """Receives binary image frames from webcam stream over HTTP POST"""
    try: 
        # read incoming bytes from payload 
        contents = await file.read()

        # convert binary string chunks into raw NumPy array data 
        nparr = np.frombuffer(contents, np.uint8)

        # decode array back into standard OpenCV BGR image matrix format 
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None: 
            return {"success": False, 
                    "error": "Invalid frame data received."}
        
        # downscale frame size to optimize speed 
        frame = cv2.resize(frame, (640, 480))

        # pipe matrix array into tracker engine 
        result = eye_tracker.track_eyes(frame)

        if session_id in ACTIVE_SESSIONS and result.get("is_looking_away") == True:
            session = ACTIVE_SESSIONS[session_id]
            with session.lock:
                if result.get("is_looking_away") == True:
                    session.gaze_flags += 1
                if result.get("is_reading_script") == True:
                    session.script_flags += 1 

        return {"success": True, 
                "data": result}

    except Exception as e: 
        return {"success": False, 
                "error": f"Internal Server Exception: {str(e)}"}

@app.post("/api/proctor/audio-tracker")
async def audio_analyzer(session_id: str, file: UploadFile = File(...)):
    """Received chunked microphone audio recording snippets."""
    temp_path = f"incoming_{file.filename}"
    try: 
        # save incoming file onto server cache temporarily 
        contents = await file.read()
        with open(temp_path, "wb") as f: 
            f.write(contents)
        
        # run it through audio pipeline 
        result = audio_tracker.analyze_audio_chunk(temp_path)

        if session_id in ACTIVE_SESSIONS and result.get("is_ai_generated") == True:
            session = ACTIVE_SESSIONS[session_id]
            with session.lock:
                session.audio_flags += 1
                if result.get("transcript"):
                    session.transcripts.append(result["transcript"])

        return {"success": True, 
                "result": result}
    
    except Exception as e:
        return {"success": False, 
                "error": str(e)}
    finally:
        # Keep the disk cache directory clean
        if os.path.exists(temp_path):
            os.remove(temp_path)

# =======================================================
# AUTOMATED ASSESSMENT EVALUATION ENDPOINT
# =======================================================
@app.post("/api/session/{session)id}/evaluate")
async def evaluate_answer(session_id: str):
    """Aggregates audio transcripts and pass to Ollama chain"""
    if session_id not in ACTIVE_SESSIONS:
        raise HTTPException(status_code=404, detail="Active interview session not found.")
        
    session = ACTIVE_SESSIONS[session_id]
    
    with session.lock:
        if not session.transcripts:
            return {
                "status": "empty",
                "message": "No answers have been transcribed or recorded yet during this session."
            }
        full_candidate_response = " ".join(session.transcripts)
    
    try: 
        evaluation_report = evaluator_chain.invoke(full_candidate_response)
        return {
            "status": "success",
            "candidate_name": session.candidate_name,
            "evaluation": evaluation_report
        }
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Local RAG Execution Error: {str(e)}")

# =======================================================
# LIVE CHATBOT ENDPOINT (Interactive Q&A)
# =======================================================
@app.post("/api/session/chat")
async def live_interview_chatbot(payload: ChatRequest):
    """Allows the user to text the RAG engine like a regular chatbot during the test."""
    try:
        bot_response = chatbot_chain.invoke(payload.user_message)
        return {"status": "success", "reply": bot_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))