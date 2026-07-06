import cv2 
import numpy as np 
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from eye_tracker import EyeTracker
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
tracker = EyeTracker(config=APP_CONFIG)

@app.post("/api/proctor/eye-tracker")
async def eye_tracker(file: UploadFile = File(...)):
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
        result = tracker.track_eyes(frame)

        return {"success": True, 
                "data": result}

    except Exception as e: 
        return {"success": False, 
                "error": f"Internal Server Exception: {str(e)}"}