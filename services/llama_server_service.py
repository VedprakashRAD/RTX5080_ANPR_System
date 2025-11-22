import logging
import subprocess
import time
import os
import requests
import json
import base64
import threading
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LlamaServerService:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LlamaServerService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        logger.info("Initializing LlamaServer Service...")
        self.port = int(os.getenv("LLAMA_SERVER_PORT", "8081"))
        self.host = "127.0.0.1"
        self.base_url = f"http://{self.host}:{self.port}"
        
        self.model_path = os.getenv("LLAMA_MODEL_PATH")
        self.mmproj_path = os.getenv("LLAMA_MMPROJ_PATH")
        self.server_path = "/home/raai/development/Refine_ALPR/llama.cpp/build/bin/llama-server"
        
        self.server_process = None
        self._ensure_server_running()
        self._initialized = True

    def _ensure_server_running(self):
        """Check if server is running, if not start it"""
        if self._check_health():
            logger.info(f"LlamaServer already running on port {self.port}")
            return

        logger.info(f"Starting LlamaServer on port {self.port}...")
        
        cmd = [
            self.server_path,
            "-m", self.model_path,
            "--mmproj", self.mmproj_path,
            "--port", str(self.port),
            "--host", self.host,
            "-c", "2048",  # Context size
            "--n-gpu-layers", "0", # CPU only
            "-t", "4"      # Threads
        ]
        
        try:
            # Start server in background
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            logger.info("Waiting for LlamaServer to start...")
            for _ in range(30):  # Wait up to 30 seconds
                if self._check_health():
                    logger.info("LlamaServer started successfully!")
                    return
                time.sleep(1)
            
            logger.error("LlamaServer failed to start within timeout")
            # Check for errors
            if self.server_process.poll() is not None:
                stdout, stderr = self.server_process.communicate()
                logger.error(f"Server output: {stdout}\n{stderr}")
                
        except Exception as e:
            logger.error(f"Failed to start LlamaServer: {e}")

    def _check_health(self) -> bool:
        """Check if server is responsive"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=1)
            return response.status_code == 200
        except:
            return False

    def extract_license_plate(self, image_input) -> Optional[str]:
        """
        Extract license plate using persistent LlamaServer
        Args:
            image_input: Path to image (str) or image bytes (bytes)
        """
        start_time = time.time()
        
        # Prepare image data
        image_data = ""
        if isinstance(image_input, bytes):
            image_data = base64.b64encode(image_input).decode('utf-8')
        elif isinstance(image_input, str) and os.path.exists(image_input):
            with open(image_input, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
        else:
            logger.error("Invalid image input")
            return None

        # SmolVLM2 Prompt Format
        prompt = "<|im_start|> User: Read the Indian license plate number from this image and return it in uppercase without any extra text.<image> Assistant:"
        
        payload = {
            "prompt": prompt,
            "image_data": [{"data": image_data, "id": 10}],
            "temperature": 0.1,
            "n_predict": 16,
            "stop": ["<|im_end|>"]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('content', '').strip()
                logger.info(f"LlamaServer result: {content} in {time.time() - start_time:.2f}s")
                return content
            else:
                logger.error(f"Server returned error: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            # Try to restart server if connection failed
            if "Connection refused" in str(e):
                self._ensure_server_running()
            return None
