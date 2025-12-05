#!/usr/bin/env python3
import os
import time
import requests
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
import hashlib
from dotenv import load_dotenv

# Suppress OpenCV camera enumeration warnings
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_CAMERA_API_PREFERENCE'] = 'NONE'

load_dotenv()

# CONFIG
CAM_IP = os.getenv("CAMERA_IP")
CAM_USER = os.getenv("CAMERA_USERNAME")
CAM_PASS = os.getenv("CAMERA_PASSWORD")
RTSP_URL = os.getenv("RTSP_URL")
API_URL = f"http://localhost:{os.getenv('API_PORT',8000)}/extract-license-plate"
GATE_PIN = int(os.getenv("GATE_PIN", 17))

SNAPSHOT_DIR = Path("snapshots")
LOG_FILE = Path("lpr.log")
SNAPSHOT_DIR.mkdir(exist_ok=True)

# No GPIO/Gate control needed

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

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

def capture_frame():
    # Handle empty RTSP_URL by falling back to dummy camera only
    source = RTSP_URL
    cap = None
    
    if source:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            cap = None
            
    # No webcam fallback - only use RTSP or dummy camera
    if cap is None:
        # Fallback to dummy
        cap = DummyVideoCapture()

    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None

def send_to_api(image_bytes):
    try:
        files = {'image': ('plate.jpg', image_bytes, 'image/jpeg')}
        r = requests.post(API_URL, files=files, timeout=30)
        if r.status_code == 200:
            return r.json()
        log(f"API error {r.status_code}")
        # Fallback to local API at localhost:8000
        try:
            local_api_url = "http://0.0.0.0:8000/extract-license-plate"
            local_response = requests.post(local_api_url, files=files, timeout=30)
            if local_response.status_code == 200:
                return local_response.json()
            else:
                log(f"Local API error {local_response.status_code}")
        except Exception as local_e:
            log(f"Local API exception: {local_e}")
    except Exception as e:
        log(f"API exception: {e}")
        # Fallback to local API at localhost:8000
        try:
            local_api_url = "http://0.0.0.0:8000/extract-license-plate"
            files = {'image': ('plate.jpg', image_bytes, 'image/jpeg')}
            local_response = requests.post(local_api_url, files=files, timeout=30)
            if local_response.status_code == 200:
                return local_response.json()
            else:
                log(f"Local API error {local_response.status_code}")
        except Exception as local_e:
            log(f"Local API exception: {local_e}")
    return {}

def detect_motion(frame1, frame2):
    if frame1 is None or frame2 is None:
        return False
    
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray1, gray2)
    
    # Motion in ROI area
    x, y, w, h = 300, 600, 800, 300
    roi_diff = diff[y:y+h, x:x+w]
    motion_score = cv2.mean(roi_diff)[0]
    
    return motion_score > 15

def main():
    log("LPR Headless Service STARTED")
    
    prev_frame = None
    last_detection = 0
    processed_hashes = set()  # Track MD5 hashes of processed images
    max_hash_history = 100   # Keep last 100 hashes to prevent memory buildup
    
    while True:
        try:
            # Capture frame
            frame = capture_frame()
            if frame is None:
                time.sleep(1)
                continue
            
            # Motion detection
            if detect_motion(prev_frame, frame):
                current_time = time.time()
                
                # Rate limiting (15 seconds to allow vehicle to pass completely)
                if current_time - last_detection < 15:
                    prev_frame = frame
                    continue
                
                log("MOTION DETECTED")
                
                # Wait for stable image (vehicle to be in good position)
                stable_frames = 0
                stable_threshold = 3  # Need 3 stable frames
                last_stable_frame = None
                
                for _ in range(10):  # Max 10 frames to wait for stability
                    time.sleep(0.2)  # Small delay between frames
                    new_frame = capture_frame()
                    if new_frame is None:
                        break
                    
                    # Check if new frame is stable compared to current frame
                    if prev_frame is not None:
                        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                        gray2 = cv2.cvtColor(new_frame, cv2.COLOR_BGR2GRAY)
                        diff = cv2.absdiff(gray1, gray2)
                        
                        # Check motion in same ROI
                        x, y, w, h = 300, 600, 800, 300
                        roi_diff = diff[y:y+h, x:x+w]
                        motion_score = cv2.mean(roi_diff)[0]
                        
                        if motion_score < 10:  # Low motion = stable
                            stable_frames += 1
                            last_stable_frame = new_frame.copy()
                            if stable_frames >= stable_threshold:
                                break
                        else:
                            stable_frames = 0
                    
                    prev_frame = new_frame
                
                # Use the best stable frame for capture
                capture_frame_to_use = last_stable_frame if last_stable_frame is not None else frame
                
                # Calculate MD5 hash of the captured frame
                frame_hash = hashlib.md5(capture_frame_to_use.tobytes()).hexdigest()
                
                # Check if this image has already been processed
                if frame_hash in processed_hashes:
                    log(f"Duplicate image detected (hash: {frame_hash[:8]}...), skipping")
                    prev_frame = frame
                    continue
                
                # Add hash to processed set
                processed_hashes.add(frame_hash)
                
                # Limit hash history size to prevent memory issues
                if len(processed_hashes) > max_hash_history:
                    # Remove oldest 20 hashes
                    old_hashes = list(processed_hashes)[:20]
                    for old_hash in old_hashes:
                        processed_hashes.discard(old_hash)
                
                log(f"New image detected (hash: {frame_hash[:8]}...)")
                
                # Save snapshot
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                snapshot_path = SNAPSHOT_DIR / f"vehicle_{ts}.jpg"
                cv2.imwrite(str(snapshot_path), capture_frame_to_use)
                log(f"Snapshot saved: {snapshot_path.name} (stable frames: {stable_frames})")
                
                # Encode image
                ret, buffer = cv2.imencode('.jpg', capture_frame_to_use)
                if ret:
                    # Send to API
                    result = send_to_api(buffer.tobytes())
                    plate = result.get("registrationNo", "")
                    if plate:
                        plate = plate.upper()
                    else:
                        plate = ""
                    
                    # Delete image after API processing
                    try:
                        if snapshot_path.exists():
                            snapshot_path.unlink()
                            log(f"✅ Deleted temp image: {snapshot_path.name}")
                    except Exception as e:
                        log(f"❌ Failed to delete temp image: {e}")
                    
                    if plate and len(plate) >= 6:
                        log(f"PLATE DETECTED: {plate}")
                    else:
                        log("No valid plate detected")
                
                last_detection = current_time
            
            prev_frame = frame
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(1)
    
    log("Service stopped")

if __name__ == "__main__":
    main()