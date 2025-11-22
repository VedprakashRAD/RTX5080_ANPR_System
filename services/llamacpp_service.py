"""
LlamaCPP Integration for License Plate OCR
Provides CLI-based inference using llama.cpp with vision models
"""
import subprocess
import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv
import cv2
import numpy as np

load_dotenv()

logger = logging.getLogger(__name__)

class LlamaCPPService:
    # Class variable to cache model loading
    _model_cache = {}
    
    def __init__(self):
        """Initialize LlamaCPP service with configuration from .env"""
        self.llama_cli_path = os.getenv("LLAMA_CLI_PATH", "./llama-llava-cli")
        self.model_path = os.getenv("LLAMA_MODEL_PATH", "./models/Qwen2-VL-2B-Instruct-Q2_K.gguf")
        self.mmproj_path = os.getenv("LLAMA_MMPROJ_PATH", "./models/mmproj-Qwen2-VL-2B-Instruct-f16.gguf")
        self.enabled = os.getenv("USE_LLAMA_CPP", "false").lower() == "true"
        # Optimization parameters
        self.threads = int(os.getenv("LLAMA_THREADS", "4"))
        self.ctx_size = int(os.getenv("LLAMA_CTX_SIZE", "2048"))
        self.cache_enabled = os.getenv("LLAMA_MODEL_CACHE", "true").lower() == "true"
        # Cache key for this model configuration
        self.cache_key = f"{self.model_path}_{self.mmproj_path}"
        
    def is_available(self) -> bool:
        """Check if LlamaCPP is available and configured"""
        if not self.enabled:
            return False
        
        # Check if CLI exists
        if not os.path.exists(self.llama_cli_path):
            logger.warning(f"LlamaCPP CLI not found at: {self.llama_cli_path}")
            return False
        
        # Check if model exists
        if not os.path.exists(self.model_path):
            logger.warning(f"LlamaCPP model not found at: {self.model_path}")
            return False
        
        # Check if mmproj exists
        if not os.path.exists(self.mmproj_path):
            logger.warning(f"LlamaCPP mmproj not found at: {self.mmproj_path}")
            return False
        
        return True
    
    def preprocess_image(self, image_path: str) -> str:
        """
        Preprocess image for faster LLM processing
        Resize and enhance the image to optimize for license plate recognition
        """
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return image_path
            
            # Get original dimensions
            h, w = img.shape[:2]
            
            # Resize to optimal size for LLM processing (max 640px on longest side)
            max_size = 640
            if max(h, w) > max_size:
                if h > w:
                    new_h = max_size
                    new_w = int(w * max_size / h)
                else:
                    new_w = max_size
                    new_h = int(h * max_size / w)
                
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Enhance contrast for better OCR
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            enhanced = cv2.merge((l, a, b))
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            # Save preprocessed image
            base_name = os.path.splitext(image_path)[0]
            processed_path = f"{base_name}_processed.jpg"
            cv2.imwrite(processed_path, enhanced, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            return processed_path
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return image_path  # Return original if preprocessing fails
    
    def extract_license_plate(self, image_path: str) -> Optional[str]:
        """
        Extract license plate using LlamaCPP CLI
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted license plate text or None on failure
        """
        if not self.is_available():
            logger.error("LlamaCPP is not available")
            return None
        
        try:
            # Preprocess image for faster processing
            processed_image_path = self.preprocess_image(image_path)
            
            # SmolVLM2-specific prompt format: <|im_start|> User: {message}<image> Assistant:
            prompt = "<|im_start|> User: Read the Indian license plate number from this image and return it in uppercase without any extra text.<image> Assistant:"
            
            # Build command with optimizations (removed --model-cache as it's not supported)
            cmd = [
                self.llama_cli_path,
                "-m", self.model_path,
                "--mmproj", self.mmproj_path,
                "--image", processed_image_path,
                "-p", prompt,
                "--temp", "0.1",      # Low temperature for deterministic output
                "--top-k", "1",       # Greedy decoding
                "-n", "16",           # Reduced max tokens for faster response
                "--threads", str(self.threads),  # Use multiple threads
                "--ctx-size", str(self.ctx_size), # Reduced context size
                "--repeat-penalty", "1.2",  # Prevent repetition
                "--mirostat", "0"     # Disable Mirostat for faster processing
            ]
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # Increased timeout for SmolVLM2
            )
            
            # Clean up processed image
            if processed_image_path != image_path and os.path.exists(processed_image_path):
                os.remove(processed_image_path)
            
            if result.returncode == 0:
                # Extract text from output
                output = result.stdout.strip()
                
                # Clean up the output (remove prompt echo if present)
                lines = output.split('\n')
                plate_text = lines[-1].strip() if lines else ""
                
                if plate_text and plate_text != "NOT_FOUND":
                    logger.info(f"LlamaCPP extracted: {plate_text}")
                    return plate_text
                else:
                    logger.warning("LlamaCPP: No plate found")
                    return None
            else:
                logger.error(f"LlamaCPP error: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("LlamaCPP timeout (>120s)")
            return None
        except Exception as e:
            logger.error(f"LlamaCPP exception: {e}")
            return None
    
    def extract_with_timing(self, image_path: str) -> Dict:
        """
        Extract license plate with timing information
        
        Returns:
            Dict with 'text', 'duration', and 'success' keys
        """
        import time
        
        start_time = time.time()
        text = self.extract_license_plate(image_path)
        duration = time.time() - start_time
        
        return {
            'text': text,
            'duration': duration,
            'success': text is not None,
            'engine': 'llamacpp'
        }