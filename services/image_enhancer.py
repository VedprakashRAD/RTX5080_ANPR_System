"""
OpenCV-based Image Enhancement for License Plates
Applies preprocessing to improve OCR accuracy
"""
import cv2
import numpy as np

class ImageEnhancer:
    @staticmethod
    def enhance_plate(image: np.ndarray) -> np.ndarray:
        """
        Apply OpenCV enhancements to license plate image
        Fast CPU-based preprocessing
        """
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 1. Contrast enhancement using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # 2. Denoising
            denoised = cv2.fastNlMeansDenoising(enhanced, None, h=10, templateWindowSize=7, searchWindowSize=21)
            
            # 3. Sharpening
            kernel = np.array([[-1, -1, -1],
                             [-1,  9, -1],
                             [-1, -1, -1]])
            sharpened = cv2.filter2D(denoised, -1, kernel)
            
            # 4. Adaptive thresholding for better text visibility
            binary = cv2.adaptiveThreshold(
                sharpened, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 
                11, 2
            )
            
            # Convert back to BGR for consistency
            result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            
            return result
            
        except Exception as e:
            print(f"⚠️ Enhancement failed: {e}, returning original")
            return image
    
    @staticmethod
    def is_sharp_enough(image: np.ndarray, threshold: float = 100.0) -> bool:
        """Check if image is sharp enough for OCR"""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            return laplacian_var > threshold
        except:
            return True  # If check fails, assume it's okay
