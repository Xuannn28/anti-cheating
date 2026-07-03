import cv2                      # handle open camera, read frames, show windows
import mediapipe as mp          # turn raw video frames into facial coordinates
import numpy as np 
from datetime import datetime
from collections import deque 

from config import APP_CONFIG
from logger import AlertLogger

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class EyeTracker: 
    def __init__(self, config):
        # initialize Google MediaPipe Face Mesh 

        # 1. Define configuration settings using the modern Tasks API
        # We use standard face styling options, but explicitly demand blendshapes/iris data
        base_options = python.BaseOptions(
            model_asset_buffer=None # We will download or link a model file if needed
        )
        
        # 2. Modern initialization of Face Landmarker
        # Note: In the tasks API, FaceLandmarker replaces the old FaceMesh module
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1
        )
        
        # Instead of failing on mp.solutions, we bypass it completely using vision.FaceLandmarker
        # We will dynamically download the mandatory task model file programmatically if missing
        self.model_path = "face_landmarker.task"
        self._ensure_model_exists()
        
        # Final Task Setup
        self.face_mesh = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=self.model_path),
                output_face_blendshapes=True,
                num_faces=1
            )
        )

        # load configuration details 
        self.config = config 
        self.ear_threshold = config['detection']['eyes']['ear_threshold']

        # Track active alerts for our visual window badges
        self.active_alerts = {
            "EYES_CLOSED": False,
            "SCRIPT_READING": False
        }

        # keep track of states across frames 
        self.last_gaze_change = datetime.now()
        self.gaze_direction = "center" 
        self.eye_ratio = 0.3  # default generic eye-openness value
        self.gaze_changes = 0
        self.alert_logger = None   # send warnings if sus happen

        # create rolling 45-frame window memory to remember eye positions
        self.gaze_history = deque(maxlen=45)

        # assign ID (0 to 477) to every point on the face. 
        # these lists contain exact ID representing the eyelids and eyeballs. (outline of eyes)
        self.LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

        # precision landmarks provided 
        self.LEFT_IRIS_CENTER = 468         # mid of left pupil
        self.LEFT_EYE_INNER_CORNER = 133    # corner of left eye near nose
        self.LEFT_EYE_OUTER_CORNER = 33     # corner of left eye near ear

    def _ensure_model_exists(self):
        """Programmatically downloads the official 5MB face asset bundle if missing"""
        import os
        import urllib.request
        if not os.path.exists(self.model_path):
            print("Downloading required face asset model tracker bundle...")
            url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            urllib.request.urlretrieve(url, self.model_path)
            print("Model setup complete.")

    def set_alert_logger(self, alert_logger):
        """Connects our warning logger system to this eye tracking class"""
        self.alert_logger = alert_logger
    
    def _calculate_ear(self, eye_points):
        """
        EAR = Eye Aspect Ratio. 
        Checks if eyes are open or closed by measuring height vs width via Euclidean Distances
        """
        # dist between top & bottom eyelids (vertical heights)
        A = np.linalg.norm(eye_points[1] - eye_points[5])
        B = np.linalg.norm(eye_points[2] - eye_points[4])

        # dist between left & right corners of eye (horizontal width)
        C = np.linalg.norm(eye_points[0] - eye_points[3])

        if C == 0: 
            return 0.0 
        
        return (A + B) / (2.0 * C)
    
    def track_eyes(self, frame):
        try: 
            self.active_alerts["EYES_CLOSED"] = False
            self.active_alerts["SCRIPT_READING"] = False

            # opencv read image in BGR color order 
            # mediapipe AI expect RGB color order, so swap 
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # feed converted frame into AI and calculate all coordinates 
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.face_mesh.detect(mp_image)

            # if candidate out of frame / cover the camera, it will be empty.
            # return the last known data 
            if not results.face_landmarks: 
                return self.gaze_direction, self.eye_ratio
            
            # grab the coordinate for first face detected 
            face_landmarks = results.face_landmarks[0]

            frame_h, frame_w = frame.shape[:2]

            # DETECT BLINKS OR DROPPED LOOKS 
            # mediapipe raw output are normalized decimal [0, 1]
            # so, multiply by the camera width/height to get real screen pixel locations
            left_eye_coords = np.array([(face_landmarks[i].x * frame_w, 
                                         face_landmarks[i].y * frame_h) for i in self.LEFT_EYE_INDICES])
            right_eye_coords = np.array([(face_landmarks[i].x * frame_w, 
                                         face_landmarks[i].y * frame_h) for i in self.RIGHT_EYE_INDICES])
            
            # run EAR function on both eyes, then take average 
            left_ear = self._calculate_ear(left_eye_coords)
            right_ear = self._calculate_ear(right_eye_coords)
            self.eye_ratio = (left_ear + right_ear) / 2.0 

            # EAR drop below threshold
            if self.eye_ratio < self.ear_threshold: 
                self.active_alerts["EYES_CLOSED"] = True
                if self.alert_logger: 
                    self.alert_logger.log_alert("EYES_CLOSED", "Suspiscious activity detected (eye closed)")
            
            # ACCURATE EYE BALL GAZE TRACKING 
            # find iris and corners positions on screen 
            inner_x = face_landmarks[self.LEFT_EYE_INNER_CORNER].x * frame_w
            outer_x = face_landmarks[self.LEFT_EYE_OUTER_CORNER].x * frame_w
            iris_x = face_landmarks[self.LEFT_IRIS_CENTER].x * frame_w

            total_eye_width = abs(outer_x - inner_x)
            if total_eye_width > 0: 
                # 0 = iris at left corner; 0.5 = centered, 1 = iris at right corner
                current_gaze_ratio = abs(iris_x - inner_x) / total_eye_width

                self.gaze_history.append(current_gaze_ratio)

                # map numerical boundaries into categorical directions 
                new_gaze = "center"
                if current_gaze_ratio < 0.38: 
                    new_gaze = "left"
                elif current_gaze_ratio > 0.62: 
                    new_gaze = "right"
                
                # SAWTOOTH ALGORITHM (SCRIPT READING DETECTOR)
                current_time = datetime.now()
                if new_gaze != self.gaze_direction:
                    self.gaze_changes += 1      
                    self.gaze_direction = new_gaze
                    self.last_gaze_change = current_time
                
                # when at least 30 frames of memory filled, analyse the pattern 
                if len(self.gaze_history) >= 30: 
                    history_list = list(self.gaze_history)

                    # compute average eye position exclude the absolute latest frame 
                    recent_avg = np.mean(history_list[-10:-2])
                    current_gaze = history_list[-1]

                    # When reading, eyes move slowly from left to right (values climb toward 0.65).
                    # When hitting the end of a line, eyes instantly snap back to the left (value drops to 0.35).
                    # If the drop happens instantly (recent average minus current gaze is a large drop)
                    # and their eyes have been moving actively (gaze_changes > 2), they are reading a script.
                    if (recent_avg - current_gaze) > 0.12 and self.gaze_changes > 2:
                        self.active_alerts["SCRIPT_READING"] = True
                        if self.alert_logger: 
                            self.alert_logger.log_alert("SCRIPT_READING", "Sawtooth eye scanning pattern flagged")
                        self.gaze_changes = 0

            return self.gaze_direction, self.eye_ratio
        
        except Exception as e:
            if self.alert_logger:
                self.alert_logger.log_alert("EYE_TRACKING_ERROR", f"Runtime exception: {str(e)}")
            return self.gaze_direction, self.eye_ratio    

if __name__ == "__main__": 
    logger = AlertLogger()
    tracker = EyeTracker(config=APP_CONFIG)
    tracker.set_alert_logger(logger)

    # fire up webcam num 0 (default laptop camera)
    cap = cv2.VideoCapture(0)
    print("Backend Active. Face the camera to initialize analysis. Press 'q' to stop.")

    while cap.isOpened(): 
        success, frame = cap.read() 
        if not success: 
            continue 

        # shrink video image to 640x480 resolution 
        frame = cv2.resize(frame, (640, 480))

        # run eye tracking function on current frame 
        gaze_dir, ear_val = tracker.track_eyes(frame)

        # text indicator on window frame 
        cv2.putText(frame, f"Gaze: {gaze_dir.upper()}", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"EAR: {ear_val:.2f}", (30, 80), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 0, 0), 2)

        badge_y = 120  # Starting Y position for the first badge
        
        if tracker.active_alerts["EYES_CLOSED"]:
            # Draw a solid red background rectangle
            cv2.rectangle(frame, (30, badge_y), (230, badge_y + 35), (0, 0, 255), -1)
            # Overlay white text on top of it
            cv2.putText(frame, "SUS: EYES CLOSED", (40, badge_y + 25), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            badge_y += 45  # Shift down in case the next badge also triggers
            
        if tracker.active_alerts["SCRIPT_READING"]:
            # Draw a solid orange background rectangle
            cv2.rectangle(frame, (30, badge_y), (250, badge_y + 35), (0, 140, 255), -1)
            # Overlay white text on top of it
            cv2.putText(frame, "SUS: SCRIPT READING", (40, badge_y + 25), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
        # show video feed on window sceen 
        cv2.imshow('Production Eye Tracker Validation', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # release webcam hardware lock so other apps can use it
    cap.release()
    cv2.destroyAllWindows()
