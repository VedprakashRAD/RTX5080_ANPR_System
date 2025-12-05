import cv2
import requests
import time
import sqlite3
import numpy as np
from datetime import datetime
import os
from dotenv import load_dotenv
from services.license_plate_service import LicensePlateService
import re

load_dotenv()

# Configuration from .env
RTSP_URL = os.getenv("RTSP_URL")
API_URL = f"http://{os.getenv('API_HOST', '0.0.0.0')}:{os.getenv('API_PORT', 8000)}/extract-license-plate"
DB_FILE = os.getenv("DB_FILE", "lpr_logs.db")
MOTION_THRESHOLD = int(os.getenv("MOTION_THRESHOLD", 15))
PLATE_ROI_X = int(os.getenv("PLATE_ROI_X", 300))
PLATE_ROI_Y = int(os.getenv("PLATE_ROI_Y", 600))
PLATE_ROI_W = int(os.getenv("PLATE_ROI_W", 800))
PLATE_ROI_H = int(os.getenv("PLATE_ROI_H", 300))
SHARPNESS_THRESHOLD = int(os.getenv("SHARPNESS_THRESHOLD", 100))

# Plate ROI coordinates
PLATE_ROI = (PLATE_ROI_X, PLATE_ROI_Y, PLATE_ROI_W, PLATE_ROI_H)

# Create database if it doesn't exist
conn = sqlite3.connect(DB_FILE)
conn.execute('''CREATE TABLE IF NOT EXISTS logs
             (id INTEGER PRIMARY KEY, plate TEXT, timestamp TEXT, type TEXT, confidence REAL)''')
conn.commit()
conn.close()

def detect_vehicle_type(plate):
    if not plate or len(plate) < 8:
        return "UNKNOWN"
    if plate[4] in "ABCD":
        return "BIKE/SCOOTER"
    elif plate[4] == "T":
        return "TRUCK/BUS"
    elif len(plate) == 9:
        return "AUTO/TAXI"
    else:
        return "CAR"

class LPRSystem:
    def __init__(self):
        self.cap = None
        self.prev_frame = None
        self.buffer = []
        self.last_plate = ""
        self.last_time = 0
        
# Dummy camera for fallback
class DummyVideoCapture:
    def __init__(self):
        self.frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "No Camera Found", (180, 180), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    def isOpened(self):
        return True
    
    def read(self):
        time.sleep(0.1) # Simulate 10 FPS
        return True, self.frame.copy()
    
    def release(self):
        pass

    def initialize_camera(self):
        try:
            source = RTSP_URL or os.getenv("RTSP_URL")
            
            if source:
                self.cap = cv2.VideoCapture(source)
                if not self.cap.isOpened():
                    self.cap = None
            
            # No webcam fallback - only use RTSP or dummy camera
            if self.cap is None:
                print("⚠️ Using Dummy Camera (No RTSP camera available)")
                self.cap = DummyVideoCapture()

            if not self.cap.isOpened():
                return False
            return True
        except Exception as e:
            print(f"Error initializing camera: {str(e)}")
            return False
    
    def detect_motion(self, curr_frame):
        if self.prev_frame is None:
            self.prev_frame = curr_frame
            return False
        diff = cv2.absdiff(self.prev_frame, curr_frame)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        motion = np.mean(gray) > MOTION_THRESHOLD
        self.prev_frame = curr_frame
        return motion
    
    def is_sharp(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() > SHARPNESS_THRESHOLD
    
    def process_frame(self, frame):
        x, y, w, h = PLATE_ROI
        roi = frame[y:y+h, x:x+w]
        
        # Motion detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if not self.detect_motion(gray):
            return frame, None
        
        # Sharpness buffer
        if self.is_sharp(roi):
            self.buffer.append(roi)
            if len(self.buffer) > 3:
                self.buffer.pop(0)
        
        # Process best frame
        if len(self.buffer) == 3:
            best = max(self.buffer, key=self.is_sharp)
            cv2.imwrite("temp_plate.jpg", best)
            
            try:
                # Process the image with our license plate service
                with open("temp_plate.jpg", "rb") as f:
                    image_bytes = f.read()
                
                license_plate_service = LicensePlateService()
                result = license_plate_service.extract_license_plate_from_bytes(image_bytes)
                
                if result != "NOT_FOUND" and result != "ERROR_PROCESSING" and result != "PROCESSING_ERROR":
                    plate_data = result if isinstance(result, dict) else {"plate": result, "valid": True}
                    plate = plate_data.get('plate', '')
                    if plate:
                        plate = re.sub(r'[^A-Z0-9]', '', str(plate).upper())
                    else:
                        plate = ''
                    
                    current_time = time.time()
                    
                    # Avoid duplicates within 10 seconds
                    if len(plate) >= 8 and (plate != self.last_plate or current_time - self.last_time > 10):
                        vehicle_type = detect_vehicle_type(plate)
                        confidence = self.is_sharp(best)
                        
                        print(f"{vehicle_type} DETECTED: {plate}")
                        
                        # Log to SQLite
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("INSERT INTO logs (plate, timestamp, type, confidence) VALUES (?, ?, ?, ?)",
                                   (plate, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), vehicle_type, confidence))
                        conn.commit()
                        conn.close()
                        
                        # Update tracking
                        self.last_plate = plate
                        self.last_time = current_time
                        
                        # Display on frame
                        cv2.putText(frame, f"{plate} - {vehicle_type}", (50, 50), 
                                  cv2.FONT_HERSHEY_DUPLEX, 1.2, (0,255,0), 3)
                        
                        self.buffer.clear()
                        return frame, {"plate": plate, "type": vehicle_type}
            
            except Exception as e:
                print(f"Processing Error: {e}")
            
            self.buffer.clear()
        
        # Draw ROI
        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
        return frame, None