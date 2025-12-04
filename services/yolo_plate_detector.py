import cv2
import numpy as np
from ultralytics import YOLO
import os
import torch
from typing import List, Tuple, Optional

# Add safe globals for YOLO model loading in PyTorch 2.6+
try:
    # Import required classes for safe globals
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.nn.modules.conv import Conv
    from torch.nn import Sequential
    
    # Use add_safe_globals at module level for PyTorch 2.6+
    if hasattr(torch.serialization, 'add_safe_globals'):
        torch.serialization.add_safe_globals([DetectionModel, Conv, Sequential])
    else:
        # For older PyTorch versions, use safe_globals context manager
        pass
except ImportError:
    pass

class YOLOPlateDetector:
    def __init__(self, model_path: str = "yolov8_license_plate2.pt", confidence_threshold: float = 0.5):
        """Initialize YOLOv8 license plate detector"""
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load YOLOv8 model with PyTorch 2.6+ compatibility"""
        try:
            if os.path.exists(self.model_path):
                # Handle PyTorch 2.6+ weights_only restriction
                try:
                    # First try normal loading
                    self.model = YOLO(self.model_path)
                except Exception as e:
                    if "weights_only" in str(e) or "Unsupported global" in str(e):
                        # Try multiple approaches for PyTorch 2.6+ compatibility
                        success = False
                        
                        # Approach 1: Try with weights_only=False (WARNING: Only use with trusted models)
                        if not success:
                            try:
                                # This is the recommended approach from PyTorch documentation
                                # Only use if you trust the source of the model file
                                self.model = YOLO(self.model_path, weights_only=False)
                                success = True
                                print("⚠️  Loaded model with weights_only=False (only safe with trusted models)")
                            except TypeError:
                                # If weights_only parameter not supported in this YOLO version
                                pass
                            except Exception:
                                pass
                        
                        # Approach 2: Try with safe_globals context manager
                        if not success:
                            try:
                                import torch
                                # Try to import all required classes (may vary by model)
                                try:
                                    from ultralytics.nn.tasks import DetectionModel
                                    safe_classes = [DetectionModel]
                                except ImportError:
                                    safe_classes = []
                                
                                try:
                                    from ultralytics.nn.modules.conv import Conv
                                    safe_classes.append(Conv)
                                except ImportError:
                                    pass
                                
                                try:
                                    from torch.nn import Sequential
                                    safe_classes.append(Sequential)
                                except ImportError:
                                    pass
                                
                                # Add more common classes that might be needed
                                try:
                                    from torch.nn.modules.conv import Conv2d
                                    safe_classes.append(Conv2d)
                                except ImportError:
                                    pass
                                
                                if hasattr(torch.serialization, 'safe_globals') and safe_classes:
                                    with torch.serialization.safe_globals(safe_classes):
                                        self.model = YOLO(self.model_path)
                                        success = True
                                elif hasattr(torch.serialization, 'add_safe_globals') and safe_classes:
                                    # For older PyTorch versions
                                    torch.serialization.add_safe_globals(safe_classes)
                                    self.model = YOLO(self.model_path)
                                    success = True
                            except Exception as safe_e:
                                # Safe globals approach failed, will try next approach
                                pass
                        
                        # Approach 3: Try with warnings suppressed
                        if not success:
                            try:
                                import warnings
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore")
                                    self.model = YOLO(self.model_path)
                                    success = True
                                    print("⚠️  Loaded model with warnings suppressed")
                            except Exception:
                                pass
                        
                        # Approach 4: Last resort - try basic loading with error handling
                        if not success:
                            try:
                                # Try to load with proper PyTorch 2.6 safe globals
                                import torch
                                import torch.nn as nn
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore")
                                    # Add required PyTorch classes to safe globals
                                    torch.serialization.add_safe_globals([
                                        nn.BatchNorm2d,
                                        nn.Conv2d,
                                        nn.Linear,
                                        nn.Module,
                                        nn.Sequential,
                                        nn.ReLU,
                                        nn.SiLU,
                                        nn.Upsample,
                                        nn.MaxPool2d,
                                        nn.AdaptiveAvgPool2d,
                                    ])
                                    
                                    try:
                                        self.model = YOLO(self.model_path)
                                        success = True
                                        print("✅ YOLOv8 model loaded with safe globals")
                                    except Exception as fallback_e:
                                        if "weights_only" in str(fallback_e):
                                            # Fallback to weights_only=False for trusted models
                                            original_load = torch.load
                                            def unsafe_load(*args, **kwargs):
                                                kwargs.setdefault('weights_only', False)
                                                return original_load(*args, **kwargs)
                                            torch.load = unsafe_load
                                            
                                            try:
                                                self.model = YOLO(self.model_path)
                                                success = True
                                                print("⚠️  Loaded model with weights_only=False (trusted model)")
                                            finally:
                                                torch.load = original_load
                                        else:
                                            raise fallback_e
                            except Exception:
                                pass
                        
                        if not success:
                            # Final fallback - raise the original error
                            raise e
                        
                    else:
                        # Re-raise non-weights_only related exceptions
                        raise e
                print(f"✅ YOLOv8 model loaded: {self.model_path}")
            else:
                print(f"❌ Model file not found: {self.model_path}")
                self.model = None
        except Exception as e:
            print(f"❌ Error loading YOLOv8 model: {e}")
            print("💡 Recommendation: Ensure the model file is from a trusted source and consider updating PyTorch/Ultralytics versions")
            self.model = None
    
    def detect_plates(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect license plates in frame
        Returns: List of (x1, y1, x2, y2, confidence) tuples
        """
        if self.model is None:
            return []
        
        try:
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            plates = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        confidence = box.conf[0].cpu().numpy()
                        plates.append((x1, y1, x2, y2, confidence))
            
            return plates
        except Exception as e:
            print(f"❌ Error detecting plates: {e}")
            return []
    
    def get_best_plate_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Get the best license plate ROI from frame
        Returns: Cropped plate image or None
        """
        plates = self.detect_plates(frame)
        
        if not plates:
            return None
        
        # Get plate with highest confidence
        best_plate = max(plates, key=lambda x: x[4])
        x1, y1, x2, y2, confidence = best_plate
        
        # Add padding around detected plate
        padding = 10
        h, w = frame.shape[:2]
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(w, x2 + padding)
        y2 = min(h, y2 + padding)
        
        # Extract ROI
        roi = frame[y1:y2, x1:x2]
        return roi if roi.size > 0 else None
    
    def draw_detections(self, frame: np.ndarray) -> np.ndarray:
        """Draw detection boxes on frame for visualization"""
        plates = self.detect_plates(frame)
        
        for x1, y1, x2, y2, confidence in plates:
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw confidence score
            label = f"Plate: {confidence:.2f}"
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return frame