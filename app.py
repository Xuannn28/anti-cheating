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
audio_tracker = AudioTracker()

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
        self.lock = threading.lock()  # protects data when frames & audio arrive same time
    
    def to_dict(self): 
        with self.lock: 
            return {
                "candidate_name": self.candidate_name,
                "metrics": {
                    "gaze_looking_away_events": self.gaze_flags,
                    "gaze_reading_events": self.script_flags,
                    "ai_generated_speech_events": self.ai_audio_flags,
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
                session.ai_audio_flags += 1
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