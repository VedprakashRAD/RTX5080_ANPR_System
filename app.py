from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os

# Suppress OpenCV camera enumeration warnings
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_CAMERA_API_PREFERENCE'] = 'NONE'

import cv2
import queue
import threading
import hashlib
from dotenv import load_dotenv

# Fix PyTorch 2.6+ weights_only issue for YOLO models
import torch
import ultralytics.nn.tasks

# Monkey patch Ultralytics to use weights_only=False
original_torch_safe_load = ultralytics.nn.tasks.torch_safe_load

def patched_torch_safe_load(file, *args, **kwargs):
    """Patched version that uses weights_only=False for trusted models"""
    try:
        return torch.load(file, map_location='cpu', weights_only=False), file
    except Exception as e:
        return original_torch_safe_load(file, *args, **kwargs)

ultralytics.nn.tasks.torch_safe_load = patched_torch_safe_load

# Load environment variables
load_dotenv()

# Import our modules
from services.yolo_plate_detector import YOLOPlateDetector
from services.license_plate_service import LicensePlateService
# from services.llama_server_service import LlamaServerService  # NOT USED - using Ollama instead
from services.vehicle_detector import VehicleDetector
from services.image_enhancer import ImageEnhancer
# MongoDB removed - using MySQL only
from services.temp_cleanup import TempFileCleanup
from utils.indian_number_plates_guide import validate_license_plate

from utils.internet_checker import check_internet_connection
from lpr_system import LPRSystem
from web_dashboard import get_dashboard_html, get_root_html

# Import multi-camera processor for integrated startup
try:
    from multi_camera_processor import MultiCameraProcessor
    MULTI_CAMERA_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Multi-camera processor not available: {e}")
    MULTI_CAMERA_AVAILABLE = False

# Configuration from .env
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
RTSP_URL = os.getenv("RTSP_URL")

import requests
import sqlite3
import time
from datetime import datetime
import numpy as np
import threading
import subprocess
import signal
import atexit

# PRODUCTION CONFIG - Adjusted for better license plate capture
ROI = (int(os.getenv("PLATE_ROI_X", 200)), int(os.getenv("PLATE_ROI_Y", 400)), 
       int(os.getenv("PLATE_ROI_W", 1000)), int(os.getenv("PLATE_ROI_H", 400)))
SHARPNESS_THRESHOLD = int(os.getenv("SHARPNESS_THRESHOLD", 50))  # Lower for easier detection
MOTION_THRESHOLD = int(os.getenv("MOTION_THRESHOLD", 5))  # Lower for easier detection
RETRY_ATTEMPTS = 2

# Thread-safe global state for stability detection
class GlobalState:
    def __init__(self):
        self.camera = None
        self.camera_lock = threading.Lock()
        self.yolo_detector = None
        self.license_plate_service = None
        self.vehicle_detector = None
        self.image_enhancer = None
        # MongoDB removed - using MySQL only
        self.temp_cleanup = None
        self.last_processed_plates = {}
        self.plate_positions = {}
        self.plate_stable_frames = {}
        self.ocr_queue = queue.Queue()
        self.ocr_worker_running = False
        self.ocr_worker_thread = None
        self.last_cleanup_time = time.time()
        self.initialize_detectors()
        self.last_detection_time = 0
        self.processed_vehicles = {}  # Tracks plate stability: {plate_key: {'bbox_history': [], 'stability_count': 0, ...}}
        self.vehicle_queue = queue.Queue()
        self.api_busy = False
        self.camera_instance = None
        self.last_frame = None
        self.last_frame_time = 0
        self.state_lock = threading.Lock()
        self.prev_frame_gray = None  # For motion detection if needed

    def initialize_detectors(self):
        print("🔄 Initializing detectors...")
        # Two-stage detection: Vehicle -> Plate
        # High-performance GPU settings with strict confidence thresholds
        self.vehicle_detector = VehicleDetector(confidence_threshold=0.6)
        self.yolo_detector = YOLOPlateDetector(model_path="models/yolov8_license_plate2.pt", confidence_threshold=0.75)
        self.image_enhancer = ImageEnhancer()
        
        # Duplicate suppression: track recent plates with timestamps
        self.recent_plates = {}  # {plate: last_seen_timestamp}
        self.duplicate_cooldown = 180  # 3 minutes
        
        # Use Ollama (qwen2.5vl:3b) for license plate extraction
        # LlamaServerService is NOT used - we use Ollama instead
        # self.license_plate_service = LlamaServerService()  # DISABLED
        self.license_plate_service = LicensePlateService()  # Uses Ollama
        
        # MongoDB removed - using MySQL only
        self.temp_cleanup = TempFileCleanup(temp_dir="temp_screenshots", max_age_hours=1)
        print("✅ Detectors initialized (CPU-optimized)")

state = GlobalState()

def detect_vehicle_type(plate):
    plate = plate.upper().replace(" ", "")
    if len(plate) < 8:
        return "UNKNOWN"
    
    p4 = plate[4] if len(plate) > 4 else ""
    if p4 in "ABCD":
        return "BIKE/SCOOTER"
    elif p4 == "T":
        return "TRUCK/BUS"
    elif len(plate) == 9 and plate[4:6].isalpha():
        return "AUTO/TAXI"
    elif len(plate) == 10:
        return "CAR"
    else:
        return "UNKNOWN"

def is_motion_detected(gray):
    global prev_gray
    if prev_gray is None:
        prev_gray = gray
        return False
    
    # Motion in ROI only
    x, y, w, h = ROI
    roi_gray = gray[y:y+h, x:x+w]
    roi_prev = prev_gray[y:y+h, x:x+w]
    
    diff = cv2.absdiff(roi_prev, roi_gray)
    motion_score = np.mean(diff)
    prev_gray = gray
    return motion_score > MOTION_THRESHOLD

def is_sharp(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() > SHARPNESS_THRESHOLD

def crop_roi(frame):
    x, y, w, h = ROI
    return frame[y:y+h, x:x+w]

def call_api_with_retry(image_bytes):
    """Call license plate API directly without HTTP request"""
    try:
        # Use Persistent LlamaServer (SmolVLM2)
        from services.llama_server_service import LlamaServerService
        ocr_service = LlamaServerService()
        result = ocr_service.extract_license_plate(image_bytes)
        
        if result:
            return {'success': True, 'registrationNo': result}
        return None
    except Exception as e:
        print(f"Direct API call failed: {e}")
        return None

def save_vehicle_image(frame, plate):
    os.makedirs('vehicle_images', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vehicle_images/{plate}_{timestamp}.jpg"
    cv2.imwrite(filename, frame)
    return filename

def save_roi_temp_image(roi_image, plate):
    os.makedirs('temp_roi', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"temp_roi/{plate}_{timestamp}_roi.jpg"
    cv2.imwrite(filename, roi_image)
    return filename

def sync_to_cloud_and_cleanup(plate, vehicle_type, full_image_path, roi_image_path, api_response):
    """
    STAGE 14: Sync to MongoDB (Optional)
    STAGE 15: Cleanup Temp Files
    """
    try:
        # MongoDB removed - using MySQL + External API instead
        pass
        
        # STAGE 15: Cleanup temp ROI image after processing
        if state.temp_cleanup and os.path.exists(roi_image_path):
            filename = os.path.basename(roi_image_path)
            state.temp_cleanup.cleanup_specific_file(filename)
                
    except Exception as e:
        print(f"❌ Cloud sync/cleanup error: {e}")

def log_to_database(plate, vehicle_type, image_path, roi_image_path, api_response):
    try:
        conn = sqlite3.connect(os.getenv("DB_FILE", "lpr_logs.db"))
        conn.execute('''CREATE TABLE IF NOT EXISTS logs
                     (id INTEGER PRIMARY KEY, plate TEXT, timestamp TEXT, type TEXT, 
                      confidence REAL, image_path TEXT, roi_image_path TEXT, api_response TEXT)''')
        
        conn.execute("INSERT INTO logs (plate, timestamp, type, confidence, image_path, roi_image_path, api_response) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (plate, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), vehicle_type, 98.5, image_path, roi_image_path, str(api_response)))
        conn.commit()
        conn.close()
        print(f"✓ DETECTED: {plate} [{vehicle_type}] → Full: {image_path} | ROI: {roi_image_path}")
    except Exception as e:
        print(f"Database error: {e}")

def process_frame_for_lpr(frame):
    """
    TWO-STAGE DETECTION PIPELINE (CPU-Optimized for Real-Time)
    Stage 1: Detect Vehicles (YOLOv8n)
    Stage 2: Detect Plates within Vehicle ROIs (YOLOv8 Plate Model)
    Stage 3: Enhance Plate Images (OpenCV)
    Stage 4: Queue for OCR Processing
    """
    current_time = time.time()
    
    # Periodic cleanup (every hour)
    if state.temp_cleanup and (current_time - state.last_cleanup_time) > 3600:
        state.temp_cleanup.cleanup_old_files()
        state.last_cleanup_time = current_time

    try:
        # Check if detectors are available
        if state.vehicle_detector is None or state.vehicle_detector.model is None:
            cv2.putText(frame, "Vehicle detector not loaded", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            return frame
        
        if state.yolo_detector is None or state.yolo_detector.model is None:
            cv2.putText(frame, "Plate detector not loaded", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            return frame

        # STAGE 1: Detect Vehicles
        vehicles = state.vehicle_detector.detect_vehicles(frame)
        
        if not vehicles:
            cv2.putText(frame, "No vehicles detected", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            return frame
        
        print(f"🚗 Detected {len(vehicles)} vehicles")
        
        # Track all detected plates across all vehicles
        all_plates = []
        
        # STAGE 2: For each vehicle, detect plates
        for v_idx, (vx1, vy1, vx2, vy2, v_conf, v_cls) in enumerate(vehicles):
            # Draw vehicle bounding box (blue)
            cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (255, 0, 0), 2)
            cv2.putText(frame, f"Vehicle {v_idx+1}", (vx1, vy1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # Extract vehicle ROI
            vehicle_roi = frame[vy1:vy2, vx1:vx2]
            if vehicle_roi.size == 0:
                continue
            
            # Detect plates within this vehicle ROI
            plates_in_vehicle = state.yolo_detector.detect_plates(vehicle_roi)
            
            # Convert plate coordinates from ROI to full frame
            for px1, py1, px2, py2, p_conf in plates_in_vehicle:
                # Translate coordinates to full frame
                full_x1 = vx1 + px1
                full_y1 = vy1 + py1
                full_x2 = vx1 + px2
                full_y2 = vy1 + py2
                
                all_plates.append((full_x1, full_y1, full_x2, full_y2, p_conf, v_idx))
        
        print(f"🔍 Detected {len(all_plates)} plates across vehicles")
        
        if not all_plates:
            cv2.putText(frame, f"{len(vehicles)} vehicles, no plates", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            return frame

        # STAGE 3 & 4: Plate Stability Detection and Processing
        with state.state_lock:
            # Clear old tracked plates (older than 30 seconds)
            state.processed_vehicles = {k: v for k, v in state.processed_vehicles.items() if current_time - v.get('first_seen', 0) < 30}

            for i, (x1, y1, x2, y2, yolo_confidence, vehicle_idx) in enumerate(all_plates):
                # Create a unique identifier for this plate
                plate_key = f"{x1//10}_{y1//10}_{x2//10}_{y2//10}_{int((x2-x1) * (y2-y1) / 100)}"

                # Initialize or update plate tracking
                if plate_key not in state.processed_vehicles:
                    state.processed_vehicles[plate_key] = {
                        'bbox_history': [(x1, y1, x2, y2)],
                        'stability_count': 0,
                        'last_seen': current_time,
                        'first_seen': current_time,
                        'last_processed': 0,
                        'confidence': yolo_confidence
                    }
                    print(f"🆕 New plate detected: {plate_key} [Stabilizing 0/3]")
                    cv2.putText(frame, f"P{i+1}: New", (x1, y1-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)
                else:
                    # Update existing plate tracking
                    state.processed_vehicles[plate_key]['last_seen'] = current_time
                    state.processed_vehicles[plate_key]['bbox_history'].append((x1, y1, x2, y2))

                    # Keep only last 5 positions for stability calculation
                    if len(state.processed_vehicles[plate_key]['bbox_history']) > 5:
                        state.processed_vehicles[plate_key]['bbox_history'] = state.processed_vehicles[plate_key]['bbox_history'][-5:]

                    # Calculate stability based on position variance
                    hist = state.processed_vehicles[plate_key]['bbox_history']
                    if len(hist) >= 3:
                        # Calculate average position
                        avg_x1 = sum([x[0] for x in hist]) / len(hist)
                        avg_y1 = sum([x[1] for x in hist]) / len(hist)
                        avg_x2 = sum([x[2] for x in hist]) / len(hist)
                        avg_y2 = sum([x[3] for x in hist]) / len(hist)

                        # Calculate variance
                        var_x1 = sum([(x[0] - avg_x1)**2 for x in hist]) / len(hist)
                        var_y1 = sum([(x[1] - avg_y1)**2 for x in hist]) / len(hist)
                        var_x2 = sum([(x[2] - avg_x2)**2 for x in hist]) / len(hist)
                        var_y2 = sum([(x[3] - avg_y2)**2 for x in hist]) / len(hist)

                        # If variance is low, plate is stable
                        stability_threshold = 15.0
                        if max(var_x1, var_y1, var_x2, var_y2) < stability_threshold:
                            state.processed_vehicles[plate_key]['stability_count'] += 1
                            current_stability = state.processed_vehicles[plate_key]['stability_count']

                            print(f"🔄 Plate {i+1}: Stabilizing {current_stability}/3 (variance: {max(var_x1, var_y1, var_x2, var_y2):.2f})")
                            cv2.putText(frame, f"P{i+1}: Stab {current_stability}/3", (x1, y1-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

                            # If stable for 3 consecutive frames AND not processed recently, capture and process
                            if (current_stability >= 3 and
                                current_time - state.processed_vehicles[plate_key]['last_processed'] >= 30):

                                # Extract ROI for the stable plate
                                padding = 15
                                h, w = frame.shape[:2]
                                x1_roi = max(0, x1 - padding)
                                y1_roi = max(0, y1 - padding)
                                x2_roi = min(w, x2 + padding)
                                y2_roi = min(h, y2 + padding)
                                plate_roi = frame[y1_roi:y2_roi, x1_roi:x2_roi].copy()

                                if plate_roi.size > 0:
                                    # STAGE 3: OpenCV Enhancement
                                    enhanced_roi = state.image_enhancer.enhance_plate(plate_roi)
                                    
                                    # Check sharpness
                                    if not state.image_enhancer.is_sharp_enough(enhanced_roi):
                                        print(f"⚠️ Plate {i+1}: Not sharp enough, skipping")
                                        continue
                                    
                                    # Save enhanced ROI
                                    os.makedirs('temp_screenshots', exist_ok=True)
                                    from datetime import timezone
                                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                                    screenshot_path = f"temp_screenshots/enhanced_plate_{i+1}_{timestamp}.jpg"
                                    cv2.imwrite(screenshot_path, enhanced_roi)
                                    print(f"📸 Stable plate {i+1} captured & enhanced! Saved: {screenshot_path}")
                                    cv2.putText(frame, f"P{i+1}: CAPTURED", (x1, y1-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

                                    # STAGE 4: Queue for OCR processing
                                    vehicle_data = {
                                        'screenshot_path': screenshot_path,
                                        'bbox': (x1, y1, x2, y2),
                                        'yolo_confidence': yolo_confidence,
                                        'timestamp': current_time,
                                        'plate_index': i,
                                        'vehicle_index': vehicle_idx
                                    }

                                    state.vehicle_queue.put(vehicle_data)
                                    print(f"📤 Queued for OCR: {screenshot_path} (Conf: {yolo_confidence:.3f})")

                                    # Update last processed time
                                    state.processed_vehicles[plate_key]['last_processed'] = current_time
                                    state.processed_vehicles[plate_key]['stability_count'] = 0

                                    # Start queue processor if not running
                                    if not state.api_busy:
                                        threading.Thread(target=process_vehicle_queue, daemon=True).start()
                                        print("📡 OCR processing thread started")
                        else:
                            # Reset stability if plate moved too much
                            state.processed_vehicles[plate_key]['stability_count'] = max(0, state.processed_vehicles[plate_key]['stability_count'] - 1)
                            print(f"🚗 Plate {i+1}: Unstable (variance: {max(var_x1, var_y1, var_x2, var_y2):.2f})")
                            cv2.putText(frame, f"P{i+1}: Moving", (x1, y1-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                    else:
                        cv2.putText(frame, f"P{i+1}: Tracking", (x1, y1-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

                # Draw plate detection box (green)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{yolo_confidence:.2f}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    except cv2.error as e:
        print(f"❌ OpenCV error: {e}")
    except (ValueError, IndexError) as e:
        print(f"❌ Data processing error: {e}")
    except Exception as e:
        print(f"❌ Unexpected LPR processing error: {e}")

    return frame

def process_single_plate(frame, x1, y1, x2, y2, yolo_confidence, current_time, plate_index):
    """Process individual plate detection"""
    try:
        # Extract ROI for this specific plate
        padding = 15
        h, w = frame.shape[:2]
        x1_roi = max(0, x1 - padding)
        y1_roi = max(0, y1 - padding)
        x2_roi = min(w, x2 + padding)
        y2_roi = min(h, y2 + padding)
        plate_roi = frame[y1_roi:y2_roi, x1_roi:x2_roi]
        
        if plate_roi.size == 0:
            return False
        
        # Generate unique hash for this specific plate
        roi_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        roi_resized = cv2.resize(roi_gray, (64, 32))
        roi_hash = hashlib.md5(f"{roi_resized.tobytes()}_{x1}_{y1}".encode()).hexdigest()
        
        # Check vehicle stability and processing status
        if roi_hash in processed_vehicles:
            vehicle_data = processed_vehicles[roi_hash]
            if isinstance(vehicle_data, dict):
                if vehicle_data.get('processed', False):
                    return False  # Already processed
                vehicle_data['count'] += 1
            else:
                processed_vehicles[roi_hash] = {'count': 1, 'first_seen': current_time, 'processed': False}
        else:
            processed_vehicles[roi_hash] = {'count': 1, 'first_seen': current_time, 'processed': False}
        
        # Require stability (3 frames)
        if processed_vehicles[roi_hash]['count'] < 3:
            cv2.putText(frame, f"V{plate_index+1}: Stabilizing {processed_vehicles[roi_hash]['count']}/3", 
                       (x1, y1-30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            return False
        
        # Sharpness check
        sharpness = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        if sharpness < SHARPNESS_THRESHOLD:
            cv2.putText(frame, f"V{plate_index+1}: Low sharpness", (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
            return False
        
        # Queue for async API processing
        import threading
        import queue
        if not hasattr(process_single_plate, 'api_queue'):
            process_single_plate.api_queue = queue.Queue()
            process_single_plate.processing = False
        
        # Save ROI and queue for processing
        os.makedirs('temp_screenshots', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"temp_screenshots/vehicle_{plate_index}_{timestamp}.jpg"
        cv2.imwrite(screenshot_path, plate_roi)
        
        # Add to queue
        process_single_plate.api_queue.put({
            'path': screenshot_path,
            'roi_hash': roi_hash,
            'bbox': (x1, y1, x2, y2),
            'confidence': yolo_confidence,
            'plate_index': plate_index
        })
        
        # Start async processor if not running
        if not process_single_plate.processing:
            threading.Thread(target=async_api_processor, daemon=True).start()
            process_single_plate.processing = True
        
        # Visual feedback
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"V{plate_index+1}: QUEUED", (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        
        return True
    
    except Exception as e:
        print(f"Error processing plate {plate_index}: {e}")
        return False

def async_api_processor():
    """Process API calls asynchronously for multiple vehicles"""
    import requests
    global processed_vehicles, processed_plates  # Declare globals at the beginning

    # Initialize processed hashes for MD5 duplicate detection
    processed_hashes = {}

    while True:
        try:
            if state.vehicle_queue.empty():
                time.sleep(0.1)
                continue

            vehicle_data = state.vehicle_queue.get(timeout=1)

            # Calculate MD5 hash of the image to prevent duplicate processing
            screenshot_path = vehicle_data['screenshot_path']
            image_hash = None
            try:
                with open(screenshot_path, 'rb') as f:
                    file_content = f.read()
                    image_hash = hashlib.md5(file_content).hexdigest()

                # Check if this image hash has been processed recently to avoid duplicates
                # Clean old hashes (older than 30 seconds)
                current_time = time.time()
                processed_hashes = {k: v for k, v in processed_hashes.items()
                                  if current_time - v['timestamp'] < 30}

                if image_hash in processed_hashes:
                    print(f"⏭️ Skipping duplicate image (hash: {image_hash[:8]}...) - processed recently")
                    # Clean up the duplicate image file
                    if os.path.exists(screenshot_path):
                        os.remove(screenshot_path)
                        print(f"🗑️ Deleted duplicate temp image: {screenshot_path}")
                    continue  # Skip this duplicate image
            except Exception as e:
                print(f"⚠️ Hash calculation error: {e}")
                # Continue processing if hash calculation fails

            # Mark this hash as processed
            if image_hash:
                processed_hashes[image_hash] = {
                    'timestamp': time.time(),
                    'bbox': vehicle_data['bbox']
                }

            # Make API call
            with open(screenshot_path, 'rb') as f:
                files = {'image': ('roi.jpg', f, 'image/jpeg')}
                response = requests.post(f"http://localhost:{API_PORT}/extract-license-plate",
                                       files=files, timeout=20)

            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('registrationNo'):
                    plate = result['registrationNo']
                    
                    # DUPLICATE SUPPRESSION: Check if plate seen recently
                    current_time = time.time()
                    if plate in state.recent_plates:
                        time_since_last = current_time - state.recent_plates[plate]
                        if time_since_last < state.duplicate_cooldown:
                            print(f"⏭️ Duplicate: {plate} (seen {time_since_last:.1f}s ago, cooldown: {state.duplicate_cooldown}s)")
                            # Clean up duplicate image
                            if os.path.exists(screenshot_path):
                                os.remove(screenshot_path)
                            continue
                    
                    # Update recent plates tracker
                    state.recent_plates[plate] = current_time
                    
                    # Clean old entries (older than 60 seconds)
                    state.recent_plates = {k: v for k, v in state.recent_plates.items() 
                                          if current_time - v < 60}
                    
                    print(f"✅ NEW DETECTION: {plate} [Vehicle {vehicle_data.get('plate_index', 0)+1}]")
                    
                    # MongoDB removed - using MySQL + External API instead
                    pass

            # Cleanup - delete the image file after processing
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                print(f"🗑️ Deleted temp image after processing: {screenshot_path}")

        except queue.Empty:
            continue
        except Exception as e:
            print(f"API processor error: {e}")
            # Even if there's an error, try to clean up the image file
            try:
                screenshot_path = vehicle_data.get('screenshot_path')
                if screenshot_path and os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                    print(f"🗑️ Deleted temp image after error: {screenshot_path}")
            except:
                pass

        # Update API busy state
        with state.state_lock:
            # Check if there are more items in queue
            state.api_busy = not state.vehicle_queue.empty()

# Global camera instance to prevent multiple connections
camera_instance = None
camera_lock = threading.Lock()
last_frame = None
last_frame_time = 0

# Global multi-camera processor instance
multi_camera_processor = None
multi_camera_thread = None

# Global YOLO detector to prevent repeated model loading
yolo_detector = None
yolo_lock = threading.Lock()

def get_shared_yolo_detector():
    """Get shared YOLO detector instance to prevent repeated model loading"""
    global yolo_detector
    with yolo_lock:
        if yolo_detector is None:
            print("🔄 Initializing shared YOLO detector...")
            yolo_detector = YOLOPlateDetector(model_path="models/yolov8_license_plate2.pt", confidence_threshold=0.8)
            print("✅ Shared YOLO detector ready")
    return yolo_detector

# Dummy camera for fallback
class DummyVideoCapture:
    def __init__(self):
        self.frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "No Camera Found", (180, 180), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(self.frame, "Check Connection", (200, 220), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1)
    
    def isOpened(self):
        return True
    
    def read(self):
        time.sleep(0.1) # Simulate 10 FPS
        return True, self.frame.copy()
    
    def release(self):
        pass
    
    def set(self, prop, val):
        pass

def get_shared_camera():
    """Get shared camera instance to prevent 429 errors"""
    global camera_instance
    with camera_lock:
        if camera_instance is None or not camera_instance.isOpened():
            if camera_instance:
                camera_instance.release()
            
            # Try RTSP first, no fallback to webcam
            if RTSP_URL:
                print(f"🔗 Trying RTSP: {RTSP_URL}")
                camera_instance = cv2.VideoCapture(RTSP_URL)
                if not camera_instance.isOpened():
                    print(f"❌ RTSP connection failed: {RTSP_URL}")
                    camera_instance = None
            
            # No webcam fallback - only use RTSP cameras
            # Fallback to dummy camera if RTSP fails
            if camera_instance is None:
                print("⚠️ Using Dummy Camera (No RTSP camera available)")
                camera_instance = DummyVideoCapture()
            
            if camera_instance.isOpened():
                camera_instance.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                camera_instance.set(cv2.CAP_PROP_FPS, 5)
                print(f"✅ Camera connected: {'Dummy' if isinstance(camera_instance, DummyVideoCapture) else 'RTSP'}")
            else:
                print(f"❌ Camera connection failed completely")
        return camera_instance

def get_latest_frame():
    """Get latest frame with caching to reduce camera access"""
    global last_frame, last_frame_time
    current_time = time.time()
    
    # Use cached frame if less than 0.5 seconds old
    if last_frame is not None and (current_time - last_frame_time) < 0.5:
        return True, last_frame
    
    # Get new frame from shared camera
    camera = get_shared_camera()
    if camera and camera.isOpened():
        ret, frame = camera.read()
        if ret:
            last_frame = frame
            last_frame_time = current_time
            # Removed frequent frame logging for performance
            return True, frame
        else:
            print("❌ Failed to read frame from camera")
    else:
        print("❌ Camera not available")
    return False, None

# OPTIMIZED LOW-LATENCY MJPEG STREAM
def generate_frames():
    while True:
        success, frame = get_latest_frame()
        if not success or frame is None:
            # Smaller placeholder (240x320)
            placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Loading...", (50, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.05)
            continue
        
        # Process frame for license plate detection
        frame = process_frame_for_lpr(frame)
        
        # Add timestamp overlay
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # OPTIMIZATION 1: Resize to 640x360 (4x smaller)
        small_frame = cv2.resize(frame, (640, 360))
        
        # OPTIMIZATION 2: Fast JPEG quality (60 instead of 80)
        ret, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # OPTIMIZATION 3: 10 FPS for better performance
        time.sleep(0.1)

# Response models
class LicensePlateResponse(BaseModel):
    success: bool
    internet: bool
    registrationNo: Optional[str] = None
    yolo_detections: Optional[list] = None
    yolo_confidence: Optional[float] = None
    error: Optional[str] = None

class LPRSystemResponse(BaseModel):
    success: bool
    message: str

# FastAPI app
app = FastAPI(title="Complete License Plate Recognition System", 
              description="Full LPR system with camera integration, vehicle detection, and web dashboard")

# Include clean API router
try:
    from api.license_plate import router as license_plate_router
    app.include_router(license_plate_router, prefix="/api", tags=["Clean ANPR API"])
    print("✅ Clean API router loaded at /api/extract-license-plate")
except Exception as e:
    print(f"⚠️ Could not load API router: {e}")


@app.get("/start-lpr", response_model=LPRSystemResponse)
async def start_lpr_system():
    """
    Start the LPR camera system
    """
    try:
        lpr = LPRSystem()
        if lpr.initialize_camera():
            return LPRSystemResponse(success=True, message="LPR system started successfully")
        else:
            return LPRSystemResponse(success=False, message="Failed to initialize camera")
    except Exception as e:
        return LPRSystemResponse(success=False, message=f"Error starting LPR system: {str(e)}")



@app.get("/vehicle-image/{filename}")
async def get_vehicle_image(filename: str):
    """
    Serve detected vehicle images
    """
    from fastapi.responses import FileResponse
    image_path = f"vehicle_images/{filename}"
    if os.path.exists(image_path):
        return FileResponse(image_path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")

@app.get("/roi-image/{filename}")
async def get_roi_image(filename: str):
    """
    Serve ROI images sent to API (temp files)
    """
    from fastapi.responses import FileResponse
    image_path = f"temp_roi/{filename}"
    if os.path.exists(image_path):
        return FileResponse(image_path)
    else:
        raise HTTPException(status_code=404, detail="ROI image not found")

@app.get("/video_feed")
async def video_feed():
    """MJPEG stream from configured RTSP URL."""
    rtsp_url = RTSP_URL or (RTSP_URLS[0] if RTSP_URLS else None)
    
    # If no RTSP URL is configured, use dummy stream
    if not rtsp_url:
        print("⚠️ No RTSP URL configured, using dummy stream")
        # Return a dummy stream instead of trying webcam
        def dummy_stream():
            while True:
                # Create a black image with text
                frame = np.zeros((240, 320, 3), dtype=np.uint8)
                cv2.putText(frame, "No RTSP Camera", (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.1)
        return StreamingResponse(dummy_stream(), media_type="multipart/x-mixed-replace; boundary=frame")
        
    return StreamingResponse(mjpeg_generator(rtsp_url), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint with system information
    """
    return get_root_html()

# COMPLETE INTEGRATED SYSTEM:
# python app.py - Starts EVERYTHING:
# 1. API Server (http://localhost:8000)
# 2. Camera Stream (http://localhost:8000/video_feed) 
# 3. Headless LPR Service (automatic vehicle detection)
# 4. API Documentation (http://localhost:8000/docs)

def start_headless_service():
    """Start headless LPR service in background"""
    global headless_process
    try:
        import sys
        import os
        # Use the same Python executable and ensure virtual environment
        python_exec = sys.executable
        env = os.environ.copy()
        # Disable camera enumeration in the subprocess as well
        env['OPENCV_LOG_LEVEL'] = 'ERROR'
        env['OPENCV_VIDEOIO_DEBUG'] = '0'
        env['OPENCV_CAMERA_API_PREFERENCE'] = 'NONE'
        headless_process = subprocess.Popen([python_exec, "lpr_headless.py"], env=env)
        print(f"🚀 Headless LPR service started (PID: {headless_process.pid})")
    except Exception as e:
        print(f"❌ Failed to start headless service: {e}")

def start_multi_camera_processor():
    """Start multi-camera processor in background thread"""
    global multi_camera_processor, multi_camera_thread
    
    if not MULTI_CAMERA_AVAILABLE:
        print("⚠️ Multi-camera processor not available")
        return
    
    try:
        print("\n🎥 Starting Multi-Camera Processor...")
        multi_camera_processor = MultiCameraProcessor()
        
        # Run in background thread
        multi_camera_thread = threading.Thread(
            target=multi_camera_processor.run,
            daemon=True,
            name="MultiCameraProcessor"
        )
        multi_camera_thread.start()
        print("✅ Multi-camera processor started")
        print("   - Gate verification enabled")
        print("   - Dual-camera matching active")
        
    except Exception as e:
        print(f"❌ Failed to start multi-camera processor: {e}")
        import traceback
        traceback.print_exc()

def stop_headless_service():
    """Stop services on exit"""
    print("👋 Stopping services...")
    
    # Stop multi-camera processor
    global multi_camera_processor
    if multi_camera_processor:
        try:
            multi_camera_processor.stop_all()
            print("✅ Multi-camera processor stopped")
        except Exception as e:
            print(f"⚠️ Error stopping multi-camera processor: {e}")
    
    # Stop LlamaServer if running
    if state.license_plate_service and hasattr(state.license_plate_service, 'shutdown'):
        state.license_plate_service.shutdown()
        
    print("✅ Services stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down...")
    stop_headless_service()
    exit(0)

if __name__ == "__main__":
    # Register cleanup handlers
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(stop_headless_service)
    
    print("="*70)
    print("🚀 Starting Complete ANPR System with Gate Verification")
    print("="*70)
    print(f"📡 API Server: http://localhost:{API_PORT}")
    print(f"📹 Camera Feed: http://localhost:{API_PORT}/video_feed")
    print(f"📚 API Docs: http://localhost:{API_PORT}/docs")
    print(f"🎥 Multi-Camera: Enabled (with dual-camera gate verification)")
    print(f"🔐 Gate Verification: Active")
    print("="*70)
    
    # Start multi-camera processor after API server starts
    def delayed_start():
        time.sleep(3)  # Wait for API server to start
        print("\n⏳ Waiting for API server to be ready...")
        time.sleep(2)
        
        # Start multi-camera processor with gate verification
        start_multi_camera_processor()
        
        # Optional: Start headless service if needed
        # start_headless_service()
    
    threading.Thread(target=delayed_start, daemon=True).start()
    
    # Start API server (blocking call)
    print("\n🌐 Starting API server...\n")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
