#!/usr/bin/env python3
"""
Enhanced app.py with YOLOv8 integration
Replace your existing ROI processing with automatic plate detection
"""

# Add this import at the top
from services.yolo_plate_detector import YOLOPlateDetector

# Initialize YOLOv8 detector globally
yolo_detector = YOLOPlateDetector()

def process_frame_for_lpr_enhanced(frame):
    """Enhanced LPR processing with YOLOv8 automatic detection"""
    global last_detection_time, last_plate
    
    try:
        # 1. Motion Detection (full frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        motion_detected = is_motion_detected(gray)
        
        # 2. YOLOv8 Automatic Plate Detection (replaces fixed ROI)
        plates = yolo_detector.detect_plates(frame)
        
        if not plates:
            cv2.putText(frame, "No plates detected", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            return frame
        
        # Get best plate (highest confidence)
        best_plate = max(plates, key=lambda x: x[4])
        x1, y1, x2, y2, yolo_confidence = best_plate
        
        # 3. Extract ROI automatically
        roi = yolo_detector.get_best_plate_roi(frame)
        if roi is None:
            return frame
        
        # 4. Sharpness Check on detected ROI
        sharpness = cv2.Laplacian(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        is_sharp_enough = sharpness > SHARPNESS_THRESHOLD
        
        # Debug info with YOLOv8 confidence
        cv2.putText(frame, f"YOLO: {yolo_confidence:.2f} Sharp: {sharpness:.1f}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        # Draw YOLOv8 detection box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"Plate: {yolo_confidence:.2f}", (x1, y1-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Skip if not sharp enough or too soon
        if not is_sharp_enough or (time.time() - last_detection_time < 3):
            return frame
        
        # 5. Save ROI image for OCR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        roi_path = f"temp_roi/yolo_roi_{timestamp}.jpg"
        cv2.imwrite(roi_path, roi)
        
        # 6. Process with existing OCR service
        try:
            with open(roi_path, 'rb') as f:
                files = {'image': ('roi.jpg', f, 'image/jpeg')}
                response = requests.post(f"http://localhost:{API_PORT}/extract-license-plate", 
                                       files=files, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success') and result.get('registrationNo'):
                    plate = result['registrationNo'].upper().replace(" ", "")
                    
                    # Enhanced visual feedback
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(frame, f"DETECTED: {plate}", (50, 50),
                               cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 0), 2)
                    cv2.putText(frame, f"YOLO: {yolo_confidence:.2f} | OCR: Success", (50, 80),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    last_plate = plate
                    last_detection_time = time.time()
                    
                    print(f"✅ YOLOv8 + OCR SUCCESS: {plate} (YOLO: {yolo_confidence:.2f})")
                    
        except Exception as e:
            print(f"❌ OCR processing error: {e}")
        
        # Cleanup temp file
        if os.path.exists(roi_path):
            os.remove(roi_path)
        
    except Exception as e:
        print(f"Enhanced LPR processing error: {e}")
    
    return frame

# Replace the existing process_frame_for_lpr function with process_frame_for_lpr_enhanced