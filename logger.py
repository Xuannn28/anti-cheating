# logger.py
from datetime import datetime

class AlertLogger:
    def __init__(self):
        pass

    def log_alert(self, alert_type, message):
        """Simulates writing an evaluation flag to a production backend database"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚨 [{timestamp}] [{alert_type}] >>> {message}\n")