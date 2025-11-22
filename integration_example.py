# Integration example for existing app.py
from services.yolo_plate_detector import YOLOPlateDetector

# In your existing LPR processing function:
def enhanced_process_frame(frame):
    # Initialize YOLOv8 detector
    yolo_detector = YOLOPlateDetector()
    
    # Get automatic ROI instead of fixed ROI
    roi = yolo_detector.get_best_plate_roi(frame)
    
    if roi is not None:
        # Use this ROI with your existing Qwen2.5-VL processing
        # Save ROI temporarily
        temp_roi_path = f"./temp_roi/auto_roi_{int(time.time())}.jpg"
        cv2.imwrite(temp_roi_path, roi)
        
        # Process with existing OCR service
        result = license_plate_service.extract_license_plate_from_image(temp_roi_path)
        
        # Clean up temp file
        os.remove(temp_roi_path)
        
        return result
    
    return None