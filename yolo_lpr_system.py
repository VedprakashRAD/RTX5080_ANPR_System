#!/usr/bin/env python3
"""
Enhanced LPR System with YOLOv8 License Plate Detection
Combines automatic plate detection with Qwen2.5-VL OCR
"""

import cv2
import os
import time
import sqlite3
from datetime import datetime
from services.yolo_plate_detector import YOLOPlateDetector
from services.license_plate_service import LicensePlateService
from utils.internet_checker import check_internet_connection
import json

class YOLOLPRSystem:
    def __init__(self):
        # Initialize components
        self.yolo_detector = YOLOPlateDetector()
        self.ocr_service = LicensePlateService()
        
        # Camera setup
        self.rtsp_url = os.getenv('RTSP_URL', 'rtsp://admin:Rasdf_1212@10.1.2.201:554/stream1')
        self.cap = None
        
        # Storage paths
        self.image_path = "./detected_vehicles/"
        self.roi_path = "./temp_roi/"
        os.makedirs(self.image_path, exist_ok=True)
        os.makedirs(self.roi_path, exist_ok=True)
        
        # Database
        self.init_database()
        
        # Processing settings
        self.last_detection_time = 0
        self.detection_cooldown = 3  # seconds between detections
        
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect('lpr_logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT,
                vehicle_type TEXT,
                timestamp TEXT,
                confidence REAL,
                image_path TEXT,
                roi_image_path TEXT,
                yolo_confidence REAL,
                api_response TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
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

    def connect_camera(self):
        """Connect to RTSP camera"""
        try:
            # Handle empty RTSP_URL by falling back to webcam 0
            source = self.rtsp_url
            self.cap = None
            
            if source and "admin:Rasdf" not in source:
                self.cap = cv2.VideoCapture(source)
                if not self.cap.isOpened():
                    self.cap = None
            
            if self.cap is None:
                if not os.getenv('RTSP_URL'):
                    print("⚠️ No RTSP URL configured, trying webcam 0")
                    self.cap = cv2.VideoCapture(0)
                    if not self.cap.isOpened():
                        self.cap = None
            
            if self.cap is None:
                print("⚠️ Using Dummy Camera (No video source available)")
                self.cap = DummyVideoCapture()

            if self.cap.isOpened():
                print(f"✅ Connected to camera: {self.rtsp_url if self.rtsp_url else 'Dummy'}")
                return True
            else:
                print(f"❌ Failed to connect to camera: {self.rtsp_url}")
                return False
        except Exception as e:
            print(f"❌ Camera connection error: {e}")
            return False
    
    def save_detection(self, plate, vehicle_type, confidence, image_path, roi_path, yolo_conf, api_response):
        """Save detection to database"""
        try:
            conn = sqlite3.connect('lpr_logs.db')
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO vehicle_logs 
                (plate, vehicle_type, timestamp, confidence, image_path, roi_image_path, yolo_confidence, api_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (plate, vehicle_type, timestamp, confidence, image_path, roi_path, yolo_conf, json.dumps(api_response)))
            
            conn.commit()
            conn.close()
            print(f"💾 Saved detection: {plate} ({vehicle_type})")
            
        except Exception as e:
            print(f"❌ Database error: {e}")
    
    def process_frame(self, frame):
        """Process frame with YOLOv8 detection + OCR"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_detection_time < self.detection_cooldown:
            return frame
        
        # Detect license plates with YOLOv8
        plates = self.yolo_detector.detect_plates(frame)
        
        if not plates:
            return self.yolo_detector.draw_detections(frame)
        
        # Process the best plate
        best_plate = max(plates, key=lambda x: x[4])  # Highest confidence
        x1, y1, x2, y2, yolo_confidence = best_plate
        
        # Extract ROI
        roi = self.yolo_detector.get_best_plate_roi(frame)
        if roi is None:
            return self.yolo_detector.draw_detections(frame)
        
        # Check internet connection
        if not check_internet_connection():
            print("❌ No internet connection - skipping OCR")
            return self.yolo_detector.draw_detections(frame)
        
        # Save images
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save full frame
        full_image_path = os.path.join(self.image_path, f"vehicle_{timestamp}.jpg")
        cv2.imwrite(full_image_path, frame)
        
        # Save ROI
        roi_image_path = os.path.join(self.roi_path, f"roi_{timestamp}.jpg")
        cv2.imwrite(roi_image_path, roi)
        
        # OCR processing
        try:
            result = self.ocr_service.extract_license_plate_from_image(roi_image_path)
            
            if result.get('success', False):
                plate = result.get('registrationNo', 'UNKNOWN')
                vehicle_type = result.get('vehicleType', 'UNKNOWN')
                ocr_confidence = result.get('confidence', 0.0)
                
                # Save to database
                self.save_detection(
                    plate, vehicle_type, ocr_confidence, 
                    full_image_path, roi_image_path, 
                    yolo_confidence, result
                )
                
                # Update detection time
                self.last_detection_time = current_time
                
                print(f"🎯 DETECTED: {plate} ({vehicle_type}) - YOLO: {yolo_confidence:.2f}, OCR: {ocr_confidence:.2f}")
                
                # Draw enhanced detection info
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, f"{plate} ({vehicle_type})", (x1, y1-30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, f"YOLO: {yolo_confidence:.2f} | OCR: {ocr_confidence:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                print(f"❌ OCR failed for detected plate (YOLO conf: {yolo_confidence:.2f})")
                
        except Exception as e:
            print(f"❌ OCR processing error: {e}")
        
        return self.yolo_detector.draw_detections(frame)
    
    def run(self):
        """Main processing loop"""
        print("🚀 Starting YOLOv8 Enhanced LPR System...")
        
        if not self.connect_camera():
            return
        
        if self.yolo_detector.model is None:
            print("❌ YOLOv8 model not loaded. Please check model file.")
            return
        
        print("✅ System ready - Processing live camera feed...")
        print("Press 'q' to quit, 's' to save current frame")
        
        frame_count = 0
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ Failed to read frame")
                    break
                
                frame_count += 1
                
                # Process every 5th frame for performance
                if frame_count % 5 == 0:
                    frame = self.process_frame(frame)
                else:
                    # Just draw existing detections
                    frame = self.yolo_detector.draw_detections(frame)
                
                # Display frame
                cv2.imshow('YOLOv8 LPR System', frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    save_path = f"manual_save_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(save_path, frame)
                    print(f"💾 Frame saved: {save_path}")
                
        except KeyboardInterrupt:
            print("\n🛑 System stopped by user")
        
        finally:
            if self.cap:
                self.cap.release()
            cv2.destroyAllWindows()
            print("✅ System shutdown complete")

if __name__ == "__main__":
    system = YOLOLPRSystem()
    system.run()