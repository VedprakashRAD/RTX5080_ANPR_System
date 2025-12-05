"""
Intelligent Vehicle Detection and ANPR Processing
Detects vehicles and license plates, sends full images to API
"""

import cv2
import numpy as np
import requests
import time
from typing import Optional, Tuple, Dict
import os
import warnings
import sys

# Add services directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix PyTorch 2.6+ weights_only issue for trusted YOLO models
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

# Suppress all warnings including PyTorch
warnings.filterwarnings('ignore')

# Import vehicle tracking service
from services.vehicle_tracking import VehicleTrackingService

class VehiclePlateDetector:
    """Detect vehicles and license plates, process full images"""
    
    def __init__(self, 
                 yolo_vehicle_model: str = "models/yolov8m.pt",
                 yolo_plate_model: str = "models/yolov8_license_plate2.pt",
                 api_url: str = "http://localhost:8000/api/extract-license-plate"):
        """Initialize detector"""
        self.api_url = api_url
        
        # Load YOLO models on GPU
        try:
            from ultralytics import YOLO
            import torch
            
            # Monkey patch Ultralytics to fix PyTorch 2.6+ weights_only issue
            import ultralytics.nn.tasks
            original_torch_safe_load = ultralytics.nn.tasks.torch_safe_load
            
            def patched_torch_safe_load(file, *args, **kwargs):
                """Patched version that uses weights_only=False for trusted models"""
                try:
                    return torch.load(file, map_location='cpu', weights_only=False), file
                except Exception as e:
                    print(f"⚠️ Fallback to original loader: {e}")
                    return original_torch_safe_load(file, *args, **kwargs)
            
            ultralytics.nn.tasks.torch_safe_load = patched_torch_safe_load
            
            # Check GPU availability
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"🎮 Using device: {device}")
            
            # Load vehicle detector on GPU
            self.vehicle_detector = YOLO(yolo_vehicle_model)
            self.vehicle_detector.to(device)
            print(f"✅ Loaded vehicle detector on {device}: {yolo_vehicle_model}")
            
            # Load plate detector on GPU
            if os.path.exists(yolo_plate_model):
                self.plate_detector = YOLO(yolo_plate_model)
                self.plate_detector.to(device)
                print(f"✅ Loaded plate detector on {device}: {yolo_plate_model}")
            else:
                self.plate_detector = None
                print(f"⚠️ Plate detector not found, will use API for all vehicles")
            
            self.device = device
            
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            import traceback
            traceback.print_exc()
            self.vehicle_detector = None
            self.plate_detector = None
            self.device = 'cpu'
    
    def detect_vehicle(self, frame: np.ndarray) -> Optional[Dict]:
        """Detect vehicle in frame"""
        if self.vehicle_detector is None:
            return None
        
        results = self.vehicle_detector(frame, conf=0.4, classes=[2, 3, 5, 7], verbose=False, device=self.device)
        
        if len(results[0].boxes) > 0:
            box = results[0].boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            
            return {
                'bbox': (x1, y1, x2, y2),
                'confidence': confidence,
                'class_id': class_id,
                'has_vehicle': True
            }
        
        return None
    
    def detect_plate(self, frame: np.ndarray) -> Optional[Dict]:
        """Detect license plate in frame"""
        if self.plate_detector is None:
            return None
        
        results = self.plate_detector(frame, conf=0.3, verbose=False, device=self.device)
        
        if len(results[0].boxes) > 0:
            box = results[0].boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            
            return {
                'bbox': (x1, y1, x2, y2),
                'confidence': confidence,
                'has_plate': True
            }
        
        return {'has_plate': False}
    
    def process_frame(self, frame: np.ndarray, camera_id: str) -> Optional[Dict]:
        """Process frame: detect vehicle and plate, send full image to API"""
        vehicle_info = self.detect_vehicle(frame)
        
        if vehicle_info is None:
            return None
        
        print(f"🚗 Vehicle detected (confidence: {vehicle_info['confidence']:.2f})")
        
        plate_info = self.detect_plate(frame)
        
        if plate_info and plate_info.get('has_plate'):
            print(f"🔍 License plate detected (confidence: {plate_info['confidence']:.2f})")
            image_type = "PLATE_VISIBLE"
        else:
            print(f"⚠️ No license plate detected (rear view or obscured)")
            image_type = "NO_PLATE"
        
        result = self.send_to_api(frame, camera_id, image_type)
        
        # Return True to indicate vehicle was detected (even if API failed)
        # This ensures cooldown timer updates
        return result if result else {'vehicle_detected': True}
    
    def send_to_api(self, frame: np.ndarray, camera_id: str, image_type: str) -> Optional[Dict]:
        """Send full frame to ANPR API"""
        try:
            temp_file = f"/tmp/{camera_id}_frame.jpg"
            cv2.imwrite(temp_file, frame)
            
            with open(temp_file, 'rb') as img:
                response = requests.post(
                    self.api_url,
                    files={"image": img},
                    data={"camera_id": camera_id, "image_type": image_type},
                    timeout=5
                )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    plate = result.get('plate')
                    vehicle_type = result.get('vehicle', {}).get('type')
                    color = result.get('vehicle', {}).get('color')
                    processing_time = result.get('processing_time_ms')
                    
                    print(f"✅ API Response: plate={plate}, type={vehicle_type}, color={color}, time={processing_time}ms")
                    return result
                else:
                    print(f"⚠️ API: {result.get('error', 'No vehicle detected')}")
            else:
                print(f"❌ API error: {response.status_code}")
        
        except Exception as e:
            print(f"❌ Error sending to API: {e}")
        
        return None


class SmartCameraProcessor:
    """Process camera feed with intelligent vehicle/plate detection"""
    
    def __init__(self, camera_id: str, rtsp_url: str):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.cap = None
        self.last_detection_time = 0
        self.detection_cooldown = 180  # 3 minutes between detections for same vehicle
        self.vehicle_detector = VehicleDetector()
        self.license_plate_service = LicensePlateService()
        self.image_enhancer = ImageEnhancer()

    def process_stream(self):
        """Process camera stream"""
        print(f"🎥 Starting camera: {self.camera_id}")
        print(f"📡 RTSP: {self.rtsp_url}")
        
        # Suppress OpenCV/FFmpeg warnings
        os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
        
        self.cap = cv2.VideoCapture(self.rtsp_url)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open camera: {self.camera_id}")
            return
        
        print(f"✅ Camera connected successfully!")
        frame_count = 0
        
        while True:
            ret, frame = self.cap.read()
            
            if not ret:
                print(f"⚠️ Failed to read frame, reconnecting...")
                time.sleep(5)
                self.cap = cv2.VideoCapture(self.rtsp_url)
                continue
            
            frame_count += 1
            
            # Process every 30 frames (1 per second at 30fps)
            if frame_count % 30 != 0:
                continue
            
            # MOTION DETECTION: Skip if no significant movement
            fg_mask = self.bg_subtractor.apply(frame)
            motion_pixels = cv2.countNonZero(fg_mask)
            
            if motion_pixels < self.motion_threshold:
                self.frames_since_motion += 1
                
                # Reset background model if no motion for too long
                if self.frames_since_motion > self.max_frames_without_motion:
                    self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                        history=500,
                        varThreshold=16,
                        detectShadows=False
                    )
                    self.frames_since_motion = 0
                continue  # Skip this frame - no motion detected
            
            # Motion detected! Reset counter
            self.frames_since_motion = 0
            print(f"🔄 Motion detected ({motion_pixels} pixels changed)")
            
            # Check cooldown
            current_time = time.time()
            if current_time - self.last_detection_time < self.detection_cooldown:
                continue
            
            # Process frame
            result = self.detector.process_frame(frame, self.camera_id)
            
            # Update cooldown timer whenever a vehicle is detected
            # (result is not None means vehicle was detected, even if API failed)
            if result:
                self.last_detection_time = current_time
                
                # Register with vehicle tracking service for cross-camera matching
                if result.get('success'):
                    tracking_data = {
                        'plate': result.get('plate'),
                        'type': result.get('vehicle', {}).get('type'),
                        'color': result.get('vehicle', {}).get('color'),
                        'confidence': result.get('confidence'),
                        'image_path': f"saved_images/{self.camera_id}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    }
                    self.tracker.register_detection(self.camera_id, tracking_data)
                
                print(f"{'='*60}")
        
        self.cap.release()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python smart_vehicle_detector.py <camera_id> <rtsp_url>")
        print("Example: python smart_vehicle_detector.py GATE1-ENTRY rtsp://admin:pass@192.168.1.101:554/stream")
        sys.exit(1)
    
    camera_id = sys.argv[1]
    rtsp_url = sys.argv[2]
    
    processor = SmartCameraProcessor(camera_id, rtsp_url)
    processor.process_stream()
