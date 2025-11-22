#!/usr/bin/env python3
"""
Hailo-accelerated Vision Service for ALPR
Uses Hailo-8L NPU for fast VLM inference (target: < 3 seconds)

This will be activated once Hailo hardware is detected.
"""

import os
import base64
import hashlib
import sys
from dotenv import load_dotenv

load_dotenv()

# Try to import Hailo
HAILO_AVAILABLE = False
try:
    from hailo_platform import Device, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams
    from hailo_platform import HEF
    import numpy as np
    HAILO_AVAILABLE = True
    print("✅ Hailo SDK available")
except ImportError:
    print("⚠️  Hailo SDK not available, using CPU fallback")

# Default prompt
DEFAULT_PROMPT = "Read the Indian license plate number from this image and return it in uppercase without any extra text."

# Simple in‑memory cache
_image_cache = {}
_CACHE_MAX_SIZE = 100

class HailoVLMInference:
    """Hailo-accelerated VLM inference"""
    
    def __init__(self, hef_path=None):
        """Initialize Hailo device and load model"""
        if not HAILO_AVAILABLE:
            raise RuntimeError("Hailo SDK not available")
        
        self.hef_path = hef_path or os.getenv("HAILO_MODEL_PATH", "/home/raai/models/hailo/vlm_model.hef")
        self.device = None
        self.network_group = None
        self.vstreams = None
        
        # Initialize device
        self._init_device()
    
    def _init_device(self):
        """Initialize Hailo device"""
        try:
            # Scan for devices
            devices = Device.scan()
            if not devices:
                raise RuntimeError("No Hailo devices found")
            
            # Use first device
            self.device = Device(devices[0])
            print(f"✅ Connected to Hailo device: {devices[0]}")
            
            # Load HEF model if path exists
            if os.path.exists(self.hef_path):
                self._load_model()
            else:
                print(f"⚠️  Model not found at {self.hef_path}")
                print("   You'll need to download a .hef model file")
        
        except Exception as e:
            print(f"❌ Failed to initialize Hailo device: {e}")
            raise
    
    def _load_model(self):
        """Load HEF model onto device"""
        try:
            hef = HEF(self.hef_path)
            
            # Configure network group
            configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
            self.network_group = self.device.configure(hef, configure_params)[0]
            
            print(f"✅ Loaded model: {self.hef_path}")
        
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            raise
    
    def infer(self, image_path: str, prompt: str = DEFAULT_PROMPT) -> str:
        """Run inference on image"""
        if not self.network_group:
            raise RuntimeError("Model not loaded")
        
        # TODO: Implement actual VLM inference
        # This is a placeholder - actual implementation depends on the specific VLM model
        # For now, return a placeholder
        return "HAILO_INFERENCE_PLACEHOLDER"
    
    def __del__(self):
        """Cleanup"""
        if self.device:
            self.device.release()


def run_vision_llm_hailo(image_path: str, prompt: str = DEFAULT_PROMPT) -> str:
    """Run VLM inference using Hailo acceleration"""
    
    # Check cache first
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return ""
    
    cache_key = hashlib.sha256(img_bytes).hexdigest()
    if cache_key in _image_cache:
        return _image_cache[cache_key]
    
    try:
        # Initialize Hailo inference
        hailo_vlm = HailoVLMInference()
        
        # Run inference
        result = hailo_vlm.infer(image_path, prompt)
        
        # Cache result
        if len(_image_cache) >= _CACHE_MAX_SIZE:
            _image_cache.pop(next(iter(_image_cache)))
        _image_cache[cache_key] = result
        
        return result
    
    except Exception as e:
        print(f"❌ Hailo inference failed: {e}")
        print("   Falling back to CPU-based Ollama")
        
        # Fallback to existing CPU implementation
        from services.vision_service import run_vision_llm
        return run_vision_llm(image_path, prompt)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run_vision_llm_hailo(sys.argv[1]))
    else:
        print("Usage: python3 hailo_vision_service.py <image_path>")
