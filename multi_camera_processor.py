"""
Multi-Camera 24/7 Monitoring System
Handles 4 cameras with batch YOLO inference for efficient GPU utilization
"""

import cv2
import numpy as np
import threading
import queue
import time
import json
import os
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Add services directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix PyTorch 2.6+ weights_only issue
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

from services.vehicle_tracking import VehicleTrackingService
from config.camera_config import CameraConfig  # Import our updated CameraConfig
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CameraThread(threading.Thread):
    """Thread for capturing frames from a single camera"""
    
    def __init__(self, camera_id: str, rtsp_url: str, frame_queue: queue.Queue, config: dict):
        super().__init__(daemon=True)
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.frame_queue = frame_queue
        self.config = config
        
        self.running = True
        self.cap = None
        self.last_frame_time = 0
        self.frame_count = 0
        self.reconnect_count = 0
        
        # Motion detection - tuned to ignore stationary vehicles
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=2000,  # Increased: learn background over longer period
            varThreshold=50,  # Increased: less sensitive to stationary objects
            detectShadows=False
        )
        self.motion_threshold = config.get('motion_threshold', 15000)  # Increased for better filtering
        self.frames_since_motion = 0
        self.max_frames_without_motion = 10
        
        # FPS control
        self.target_fps = config.get('target_fps', 1)
        self.frame_interval = 30 // self.target_fps if self.target_fps > 0 else 30
        
        logger.info(f"[{self.camera_id}] Thread initialized")
    
    def connect(self) -> bool:
        """Connect to camera"""
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if self.cap.isOpened():
                logger.info(f"[{self.camera_id}] Connected to {self.rtsp_url}")
                return True
            else:
                logger.error(f"[{self.camera_id}] Failed to open camera")
                return False
        except Exception as e:
            logger.error(f"[{self.camera_id}] Connection error: {e}")
            return False
    
    def reconnect(self):
        """Reconnect to camera"""
        logger.warning(f"[{self.camera_id}] Reconnecting...")
        if self.cap:
            self.cap.release()
        
        time.sleep(2)
        self.reconnect_count += 1
        
        if self.connect():
            logger.info(f"[{self.camera_id}] Reconnected (attempt #{self.reconnect_count})")
        else:
            logger.error(f"[{self.camera_id}] Reconnection failed")
    
    def detect_motion(self, frame: np.ndarray) -> bool:
        """Detect significant motion (approaching vehicle), not stationary objects"""
        # Apply background subtraction with learning rate
        # Higher learning rate = faster adaptation to stationary objects
        learning_rate = 0.01  # Slow learning to properly detect motion
        fg_mask = self.bg_subtractor.apply(frame, learningRate=learning_rate)
        
        # Apply morphological operations to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        
        # Count motion pixels
        motion_pixels = cv2.countNonZero(fg_mask)
        
        # Find contours to detect significant moving objects
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check for significant moving objects (vehicles approaching)
        significant_motion = False
        max_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            max_area = max(max_area, area)
            # Only consider large moving objects (vehicles)
            # Increased threshold to filter out stationary vehicles
            if area > 20000:  # Minimum area for a moving vehicle
                significant_motion = True
                break
        
        if not significant_motion or motion_pixels < self.motion_threshold:
            self.frames_since_motion += 1
            
            # Reset background model if no motion for too long
            if self.frames_since_motion > self.max_frames_without_motion:
                self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                    history=2000,
                    varThreshold=50,
                    detectShadows=False
                )
                self.frames_since_motion = 0
            return False
        
        # Significant motion detected (vehicle approaching)
        self.frames_since_motion = 0
        return True
    
    def run(self):
        """Main capture loop"""
        if not self.connect():
            logger.error(f"[{self.camera_id}] Initial connection failed")
            return
        
        logger.info(f"[{self.camera_id}] Capture loop started")
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning(f"[{self.camera_id}] Failed to read frame")
                    self.reconnect()
                    continue
                
                self.frame_count += 1
                
                # FPS control - process every Nth frame
                if self.frame_count % self.frame_interval != 0:
                    continue
                
                # Motion detection
                if not self.detect_motion(frame):
                    continue
                
                # Put frame in queue (drop old if full)
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                
                self.frame_queue.put({
                    'camera_id': self.camera_id,
                    'frame': frame,
                    'timestamp': time.time()
                })
                
                self.last_frame_time = time.time()
                
            except Exception as e:
                logger.error(f"[{self.camera_id}] Error in capture loop: {e}")
                self.reconnect()
                time.sleep(5)
        
        if self.cap:
            self.cap.release()
        logger.info(f"[{self.camera_id}] Capture loop stopped")
    
    def stop(self):
        """Stop the thread"""
        self.running = False


class BatchProcessor:
    """Processes frames from multiple cameras in batches"""
    
    def __init__(self, yolo_vehicle_model: str, yolo_plate_model: str, api_url: str):
        self.api_url = api_url
        
        # Load YOLO models on GPU
        from ultralytics import YOLO
        import torch
        
        # Monkey patch for PyTorch 2.6+
        import ultralytics.nn.tasks
        original_torch_safe_load = ultralytics.nn.tasks.torch_safe_load
        
        def patched_torch_safe_load(file, *args, **kwargs):
            try:
                return torch.load(file, map_location='cpu', weights_only=False), file
            except Exception as e:
                return original_torch_safe_load(file, *args, **kwargs)
        
        ultralytics.nn.tasks.torch_safe_load = patched_torch_safe_load
        
        # Check GPU
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"🎮 Using device: {device}")
        
        # Load models
        self.vehicle_detector = YOLO(yolo_vehicle_model)
        self.vehicle_detector.to(device)
        logger.info(f"✅ Loaded vehicle detector on {device}: {yolo_vehicle_model}")
        
        if os.path.exists(yolo_plate_model):
            self.plate_detector = YOLO(yolo_plate_model)
            self.plate_detector.to(device)
            logger.info(f"✅ Loaded plate detector on {device}: {yolo_plate_model}")
        else:
            self.plate_detector = None
            logger.warning(f"⚠️ Plate detector not found: {yolo_plate_model}")
        
        self.device = device
        self.last_detection_times = {}  # {camera_id: timestamp}
        self.detection_cooldown = 180
    
    def detect_vehicle(self, frame: np.ndarray) -> Optional[Dict]:
        """Detect vehicle in frame"""
        results = self.vehicle_detector.predict(
            frame,
            conf=0.4,
            device=self.device,
            verbose=False
        )
        
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = self.vehicle_detector.names[cls_id]
                
                # Check if it's a vehicle
                if cls_name in ['car', 'motorcycle', 'bus', 'truck']:
                    return {
                        'class': cls_name,
                        'confidence': float(box.conf[0]),
                        'bbox': box.xyxy[0].tolist()
                    }
        
        return None
    
    def detect_plate(self, frame: np.ndarray) -> Optional[Dict]:
        """Detect license plate in frame"""
        if self.plate_detector is None:
            return None
        
        results = self.plate_detector.predict(
            frame,
            conf=0.3,
            device=self.device,
            verbose=False
        )
        
        for result in results:
            if len(result.boxes) > 0:
                box = result.boxes[0]
                return {
                    'has_plate': True,
                    'confidence': float(box.conf[0]),
                    'bbox': box.xyxy[0].tolist()
                }
        
        return {'has_plate': False}
    
    def send_to_api(self, frame: np.ndarray, camera_id: str, image_type: str, vehicle_info: Dict = None) -> Optional[Dict]:
        """Send frame to API for processing"""
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            
            # Send to API with YOLO vehicle detection as fallback
            files = {'image': ('frame.jpg', buffer.tobytes(), 'image/jpeg')}
            data = {
                'camera_id': camera_id,
                'image_type': image_type
            }
            
            # Add YOLO vehicle class as fallback
            if vehicle_info:
                data['yolo_vehicle_class'] = vehicle_info.get('class', 'UNKNOWN')
                data['yolo_confidence'] = str(vehicle_info.get('confidence', 0.0))
            
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result
            
        except Exception as e:
            logger.error(f"[{camera_id}] API error: {e}")
        
        return None
    
    def process_frame(self, camera_id: str, frame: np.ndarray) -> Optional[Dict]:
        """Process a single frame"""
        # Check cooldown
        current_time = time.time()
        last_time = self.last_detection_times.get(camera_id, 0)
        if current_time - last_time < self.detection_cooldown:
            return None
        
        # Detect vehicle
        vehicle_info = self.detect_vehicle(frame)
        if vehicle_info is None:
            return None
        
        logger.info(f"[{camera_id}] 🚗 Vehicle detected (confidence: {vehicle_info['confidence']:.2f})")
        
        # Detect plate
        plate_info = self.detect_plate(frame)
        
        if plate_info and plate_info.get('has_plate'):
            logger.info(f"[{camera_id}] 🔍 License plate detected (confidence: {plate_info['confidence']:.2f})")
            image_type = "PLATE_VISIBLE"
        else:
            logger.info(f"[{camera_id}] ⚠️ No license plate detected (rear view or obscured)")
            image_type = "NO_PLATE"
        
        # Send to API with YOLO vehicle info as fallback
        result = self.send_to_api(frame, camera_id, image_type, vehicle_info)
        
        if result:
            plate = result.get('plate')
            vehicle_type = result.get('vehicle', {}).get('type')
            color = result.get('vehicle', {}).get('color')
            processing_time = result.get('processing_time_ms')
            
            logger.info(f"[{camera_id}] ✅ API Response: plate={plate}, type={vehicle_type}, color={color}, time={processing_time}ms")
            
            # Update cooldown
            self.last_detection_times[camera_id] = current_time
            
            return result
        
        # Even if API failed, update cooldown to prevent spam
        self.last_detection_times[camera_id] = current_time
        return {'vehicle_detected': True}


class MultiCameraProcessor:
    """Main processor for multiple cameras"""
    
    def __init__(self, config_path: str = 'config/cameras.json'):
        # Load configuration using our updated CameraConfig class
        self.camera_config = CameraConfig(config_path)
        self.cameras = {cam['id']: cam for cam in self.camera_config.get_enabled_cameras()}
        self.processing_config = self.camera_config.settings or {}
        
        # Create frame queues
        max_queue_size = self.processing_config.get('max_queue_size', 10)
        self.frame_queues = {
            cam_id: queue.Queue(maxsize=max_queue_size)
            for cam_id in self.cameras.keys()
        }
        
        # Initialize batch processor
        self.processor = BatchProcessor(
            yolo_vehicle_model='models/yolov8m.pt',
            yolo_plate_model='models/yolov8_license_plate2.pt',
            api_url='http://localhost:8000/api/extract-license-plate'
        )
        
        # Initialize vehicle tracking
        self.tracker = VehicleTrackingService()
        
        # Camera threads
        self.camera_threads = {}
        
        logger.info(f"✅ Multi-camera processor initialized with {len(self.cameras)} cameras")
    
    def start_all_cameras(self):
        """Start all camera threads"""
        for cam_id, cam_config in self.cameras.items():
            thread = CameraThread(
                camera_id=cam_id,
                rtsp_url=cam_config['rtsp_url'],
                frame_queue=self.frame_queues[cam_id],
                config=self.processing_config
            )
            thread.start()
            self.camera_threads[cam_id] = thread
            logger.info(f"[{cam_id}] Started camera thread")
        
        logger.info("✅ All camera threads started")
    
    def process_loop(self):
        """Main processing loop"""
        logger.info("🚀 Starting processing loop...")
        
        while True:
            try:
                # Collect frames from all cameras
                for cam_id, frame_queue in self.frame_queues.items():
                    if not frame_queue.empty():
                        frame_data = frame_queue.get()
                        
                        # Process frame
                        result = self.processor.process_frame(
                            frame_data['camera_id'],
                            frame_data['frame']
                        )
                        
                        # Register with tracking service
                        if result and result.get('success'):
                            tracking_data = {
                                'plate': result.get('plate'),
                                'type': result.get('vehicle', {}).get('type'),
                                'color': result.get('vehicle', {}).get('color'),
                                'confidence': result.get('confidence'),
                                'image_path': f"saved_images/{cam_id}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                            }
                            self.tracker.register_detection(cam_id, tracking_data)
                            logger.info(f"{'='*60}")
                
                time.sleep(0.01)  # Small sleep to prevent CPU spinning
                
            except KeyboardInterrupt:
                logger.info("⚠️ Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}")
                time.sleep(1)
    
    def health_check(self):
        """Monitor camera health"""
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            for cam_id, thread in self.camera_threads.items():
                if not thread.is_alive():
                    logger.error(f"[{cam_id}] ❌ Thread died! Restarting...")
                    # Restart thread
                    new_thread = CameraThread(
                        camera_id=cam_id,
                        rtsp_url=self.cameras[cam_id]['rtsp_url'],
                        frame_queue=self.frame_queues[cam_id],
                        config=self.processing_config
                    )
                    new_thread.start()
                    self.camera_threads[cam_id] = new_thread
                
                # Check last frame time
                last_frame_age = time.time() - thread.last_frame_time
                if last_frame_age > 60 and thread.last_frame_time > 0:
                    logger.warning(f"[{cam_id}] ⚠️ No frames for {last_frame_age:.0f}s")
    
    def stop_all(self):
        """Stop all camera threads"""
        logger.info("🛑 Stopping all cameras...")
        for thread in self.camera_threads.values():
            thread.stop()
        
        for thread in self.camera_threads.values():
            thread.join(timeout=5)
        
        logger.info("✅ All cameras stopped")
    
    def run(self):
        """Run the multi-camera system"""
        try:
            # Start all cameras
            self.start_all_cameras()
            
            # Start health check thread
            health_thread = threading.Thread(target=self.health_check, daemon=True)
            health_thread.start()
            
            # Run processing loop
            self.process_loop()
            
        except KeyboardInterrupt:
            logger.info("⚠️ Shutting down...")
        finally:
            self.stop_all()


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("🎥 Multi-Camera 24/7 Monitoring System")
    logger.info("="*60)
    
    processor = MultiCameraProcessor()
    processor.run()
