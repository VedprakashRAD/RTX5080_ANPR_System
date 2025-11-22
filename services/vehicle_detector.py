"""
CPU-Optimized Vehicle Detector using YOLOv8n
Detects vehicles (car, truck, bus, motorcycle) before plate detection
"""
import cv2
import numpy as np
from ultralytics import YOLO
import os
import torch
from typing import List, Tuple, Optional

class VehicleDetector:
    def __init__(self, confidence_threshold: float = 0.4):
        """Initialize YOLOv8n vehicle detector (CPU optimized)"""
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck in COCO dataset
        self.load_model()
    
    def load_model(self):
        """Load YOLOv8n model (smallest, fastest for CPU)"""
        try:
            # Use YOLOv8n (nano) - fastest for CPU
            self.model = YOLO('yolov8n.pt')
            print("✅ YOLOv8n vehicle detector loaded (CPU optimized)")
        except Exception as e:
            print(f"❌ Error loading vehicle detector: {e}")
            self.model = None
    
    def detect_vehicles(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float, int]]:
        """
        Detect vehicles in frame (CPU optimized)
        Returns: List of (x1, y1, x2, y2, confidence, class_id) tuples
        """
        if self.model is None:
            return []
        
        try:
            # CPU optimization: reduce image size for faster inference
            h, w = frame.shape[:2]
            scale = 640 / max(h, w)  # Scale to 640px max dimension
            if scale < 1:
                new_w, new_h = int(w * scale), int(h * scale)
                small_frame = cv2.resize(frame, (new_w, new_h))
            else:
                small_frame = frame
                scale = 1.0
            
            # Run inference with CPU optimizations
            results = self.model(
                small_frame, 
                conf=self.confidence_threshold,
                verbose=False,
                device='cpu',  # Force CPU
                half=False,    # No FP16 on CPU
                imgsz=640      # Fixed size for speed
            )
            
            vehicles = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        cls = int(box.cls[0].cpu().numpy())
                        # Only keep vehicle classes
                        if cls in self.vehicle_classes:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                            confidence = float(box.conf[0].cpu().numpy())
                            
                            # Scale back to original size
                            if scale < 1:
                                x1, y1, x2, y2 = int(x1/scale), int(y1/scale), int(x2/scale), int(y2/scale)
                            
                            vehicles.append((x1, y1, x2, y2, confidence, cls))
            
            return vehicles
        except Exception as e:
            print(f"❌ Error detecting vehicles: {e}")
            return []
    
    def get_vehicle_rois(self, frame: np.ndarray) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
        """
        Get vehicle ROIs for plate detection
        Returns: List of (roi_image, (x1, y1, x2, y2)) tuples
        """
        vehicles = self.detect_vehicles(frame)
        rois = []
        
        for x1, y1, x2, y2, conf, cls in vehicles:
            # Add padding for better plate detection
            padding = 20
            h, w = frame.shape[:2]
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                rois.append((roi, (x1, y1, x2, y2)))
        
        return rois
