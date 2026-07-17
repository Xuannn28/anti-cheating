import os
import cv2 
import numpy as np 
import threading
import tempfile
import uuid
import json
import random
from typing import Dict
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
llm = ChatOllama(model="llama3.2:1b", temperature=0.0)

# =======================================================
# LOCAL RAG PIPELINE
# =======================================================

# load vector database 
vectore_store = Chroma(
    persist_directory=DB_DIR, 
    embedding_function=embeddings
)

# 1. Chatbot Retriever
chatbot_retriever = vectore_store.as_retriever(
    search_kwargs={
        "k": 3,
        "filter": {"category": "rules"}  # Enforces rules-only matching
    }
)

# 2. Evaluator Retriever
evaluator_retriever = vectore_store.as_retriever(
    search_kwargs={
        "k": 3,
        "filter": {"category": "rubrics"}  # Enforces rubric-only matching
    }
)

# Format helper to clean up database outputs for the prompt
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# tell LLM how to act using our system guidelines 
# context: the place where LangChain paste the matching paragraph from ChromaDB 

# --- PIPELINE 1: The Live Chatbot Brain ---
# --- PIPELINE 1: The Live Chatbot Brain ---
chatbot_instruction = (
    "You are a helpful AI Proctor Assistant. You answer questions using ONLY the context below.\n"
    "Rules:\n"
    "1. Provide a direct, short answer based on the Context.\n"
    "2. If the context does not contain the answer, reply exactly with: "
    "'I am sorry, I can only answer clear questions regarding exam rules and schedules.'\n\n"
    "Context:\n{context}"
)

chatbot_prompt = ChatPromptTemplate.from_messages([
    ("system", chatbot_instruction),
    ("human", "{input}")
])

chatbot_chain = (
    {"context": chatbot_retriever | format_docs, "input": RunnablePassthrough()}
    | chatbot_prompt
    | llm
    | StrOutputParser()
)

# --- PIPELINE 2: The Automated Evaluator Brain ---
evaluator_instruction = (
    "You are an objective Technical Interview Assessment Bot.\n"
    "Your ONLY job is to grade the Candidate's Input Response using the context rubrics provided.\n\n"
    "EVALUATION INSTRUCTIONS:\n"
    "1. Read the text inside <candidate_response>.\n"
    "2. Compare it against the technical concept expectations found in the Context Rubrics.\n"
    "3. Provide a clear numerical score out of 5 (e.g., Score: X/5).\n"
    "4. Detail what technical keywords were missing or correctly used.\n"
    "5. CRITICAL: Do not describe the API layout, code, or endpoints. Focus entirely on the candidate's technical explanation.\n\n"
    "Context Rubrics:\n{context}\n"
)
evaluator_prompt = ChatPromptTemplate.from_messages([
    ("system", evaluator_instruction),
    ("human", "<candidate_response>\n{input}\n</candidate_response>")
])
# Clean LCEL pipeline tailored specifically for grading reports
evaluator_chain = (
    {"context": evaluator_retriever | format_docs, "input": RunnablePassthrough()}
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
        self.assigned_topics = []
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

# Helper to safely load questions from your new file
def load_question_bank():
    try:
        with open("questions.json", "r") as f:
            return json.load(f)
    except Exception:
        # Fallback safeguard if the JSON file is missing or corrupted
        return [
            {"title": "Default Topic A", "description": "Explain Python's GIL mechanism."},
            {"title": "Default Topic B", "description": "Describe a technical disagreement you resolved."}
        ]

@app.get("/api/session/{session_id}/topics")
async def get_exam_topics(session_id: str):
    """Selects and locks in random exam questions from the file bank for this session."""
    if session_id not in ACTIVE_SESSIONS:
        raise HTTPException(status_code=404, detail="Session expired or not found")
        
    session = ACTIVE_SESSIONS[session_id]
    
    with session.lock:
        # If topics haven't been picked for this candidate yet, pick them now!
        if not session.assigned_topics:
            question_bank = load_question_bank()
            
            # Dynamically pull exactly 1 random question from the bank
            if question_bank:
                session.assigned_topics = random.sample(question_bank, k=1)
            else:
                session.assigned_topics = [{"title": "Default Topic", "description": "Please explain your technical background."}]
            
        return {"topics": session.assigned_topics}
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
    """Received chunked microphone audio recording snippets safely in temp directory."""
    
    # FIX: Save the temporary file to the OS temp folder, NOT the project directory
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"incoming_{session_id}_{file.filename}")
    
    try: 
        # save incoming file onto server cache temporarily 
        contents = await file.read()
        with open(temp_path, "wb") as f: 
            f.write(contents)
        
        # run it through audio pipeline 
        result = audio_tracker.analyze_audio_chunk(temp_path)

        if session_id in ACTIVE_SESSIONS:
            session = ACTIVE_SESSIONS[session_id]
            with session.lock:
                # Flag metric if AI characteristics are detected
                if result.get("is_ai_generated") == True:
                    session.audio_flags += 1
                
                raw_transcript = result.get("transcript", "").strip()
                
                # Always record the transcript if speech is detected
                if raw_transcript and len(raw_transcript.split()) > 2:
                    session.transcripts.append(raw_transcript)
                    print(f"[Audio Log] Valid transcript saved: {raw_transcript}")
                else:
                    print(f"[Audio Log] Dropped low-quality/fragmented audio text chunk.")

        return {"success": True, "result": result}
    
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Keep the disk cache directory clean
        if os.path.exists(temp_path):
            os.remove(temp_path)

# =======================================================
# AUTOMATED ASSESSMENT EVALUATION ENDPOINT
# =======================================================
@app.post("/api/session/{session_id}/evaluate")
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
        # 1. Retrieve the matching chunks manually so we can inspect the generated text layout
        docs = chatbot_retriever.invoke(payload.user_message)
        formatted_context = format_docs(docs)
        
        # 2. Format the prompt explicitly into standard message structures for tracking
        actual_prompt_messages = chatbot_prompt.format_messages(
            context=formatted_context, 
            input=payload.user_message
        )
        # Convert it cleanly to readable text lines
        readable_prompt_log = "\n".join([msg.content for msg in actual_prompt_messages])

        # 3. Run the invocation chain layout
        bot_response = chatbot_chain.invoke(payload.user_message)
        
        return {
            "status": "success", 
            "reply": bot_response, 
            "debug_prompt_sent": readable_prompt_log, # Returns exact text fed to Ollama
            "retrieved_chunks_count": len(docs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =======================================================
# MAIN RUNNER (Added to allow execution via `python app.py`)
# =======================================================
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)