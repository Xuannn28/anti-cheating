# config.py

APP_CONFIG = {
    'detection': {
        'eyes': {
            'gaze_threshold': 15,          # Keeping structural config variable names
            'ear_threshold': 0.05,         # Eye Aspect Ratio threshold (below this = closed)
            'consec_frames': 3             # Number of continuous frames needed to confirm a state
        }
    }
}