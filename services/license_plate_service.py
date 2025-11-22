import requests
import json
import logging
import os
import base64
from dotenv import load_dotenv
from utils.indian_number_plates_guide import validate_license_plate
from utils.internet_checker import check_internet_connection
import threading
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from .env
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5vl:3b")
REMOTE_API_URL = os.getenv("REMOTE_API_URL", "http://rnd.readyassist.net:8000/analyze/extract-license-plate")

class LicensePlateService:
    # Cache for recent results to avoid reprocessing
    _result_cache = {}
    _cache_lock = threading.Lock()
    _cache_ttl = 30  # Cache results for 30 seconds
    
    def __init__(self, ollama_host=None, compare_engines=False):
        """
        Initialize the LicensePlateService
        
        Args:
            ollama_host (str): The host URL for Ollama service
            compare_engines (bool): If True, run both Ollama and LlamaCPP in parallel for comparison
        """
        self.ollama_host = ollama_host or OLLAMA_HOST
        self.model_name = MODEL_NAME
        self.remote_api_url = REMOTE_API_URL
        self.compare_engines = compare_engines or os.getenv("COMPARE_ENGINES", "false").lower() == "true"
        
        # Initialize LlamaCPP service
        try:
            from services.llamacpp_service import LlamaCPPService
            self.llamacpp_service = LlamaCPPService()
        except ImportError:
            self.llamacpp_service = None
            logger.warning("LlamaCPP service not available")
    
    def _get_cache_key(self, image_bytes):
        """Generate cache key from image bytes"""
        import hashlib
        return hashlib.md5(image_bytes).hexdigest()
    
    def _get_cached_result(self, cache_key):
        """Get result from cache if available and not expired"""
        with self._cache_lock:
            if cache_key in self._result_cache:
                result, timestamp = self._result_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return result
                else:
                    # Remove expired entry
                    del self._result_cache[cache_key]
        return None
    
    def _set_cached_result(self, cache_key, result):
        """Store result in cache"""
        with self._cache_lock:
            self._result_cache[cache_key] = (result, time.time())
    
    def extract_license_plate_from_bytes(self, image_bytes):
        """
        Extract license plate number from image bytes using either remote or local API based on internet connectivity
        
        Args:
            image_bytes (bytes): Image data as bytes
            
        Returns:
            str: Extracted license plate number or error message
        """
        # Check cache first
        cache_key = self._get_cache_key(image_bytes)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            logger.info("Using cached result")
            return cached_result
        
        # Check internet connectivity
        internet_available = check_internet_connection()
        
        # If remote API URL is configured and internet is available, try remote API first
        if self.remote_api_url and self.remote_api_url.strip() != "" and internet_available:
            result = self._extract_with_remote_api(image_bytes)
            # If remote API fails, fallback to local API
            if result in ["ERROR_PROCESSING", "PROCESSING_ERROR"] or (isinstance(result, dict) and not result.get('plate')):
                result = self._extract_with_local_api(image_bytes)
        else:
            # Use local Ollama API when no internet or remote API not configured
            result = self._extract_with_local_api(image_bytes)
        
        # Cache the result
        self._set_cached_result(cache_key, result)
        return result
    
    def _extract_with_remote_api(self, image_bytes):
        """
        Extract license plate using remote API
        
        Args:
            image_bytes (bytes): Image data as bytes
            
        Returns:
            str: Extracted license plate number or error message
        """
        # If remote API URL is not configured, fallback to local API
        if not self.remote_api_url or self.remote_api_url.strip() == "":
            return self._extract_with_local_api(image_bytes)
            
        try:
            files = {
                'file': ('plate_image.jpg', image_bytes, 'image/jpeg'),
                'model': (None, self.model_name)
            }
            
            response = requests.post(
                self.remote_api_url,
                files=files,
                headers={'accept': 'application/json'},
                timeout=60
            )
            
            if response.status_code == 200:
                response_data = response.json()
                # Handle different response formats from remote API
                if isinstance(response_data, dict):
                    if 'registrationNo' in response_data:
                        license_plate = response_data['registrationNo']
                    elif 'plate' in response_data:
                        license_plate = response_data['plate']
                    else:
                        license_plate = str(response_data)
                else:
                    license_plate = str(response_data)
                
                if license_plate and license_plate not in ['NOT_FOUND', 'ERROR_PROCESSING', 'PROCESSING_ERROR', '']:
                    return {'plate': license_plate, 'valid': True, 'type': 'UNKNOWN'}
                else:
                    return "NOT_FOUND"
            else:
                logger.error(f"Remote API request failed with status {response.status_code}: {response.text}")
                # Fallback to local API if remote API fails
                return self._extract_with_local_api(image_bytes)
                
        except Exception as e:
            logger.error(f"Error with remote API: {str(e)}")
            # Fallback to local API if remote API fails
            return self._extract_with_local_api(image_bytes)
    
    def _extract_with_local_api(self, image_bytes):
        """
        Extract license plate using local Ollama API with retry logic
        
        Args:
            image_bytes (bytes): Image data as bytes
            
        Returns:
            str: Extracted license plate number or error message
        """
        import time
        max_retries = 1
        
        for attempt in range(max_retries):
            try:
                # Convert image bytes to base64
                image_data = base64.b64encode(image_bytes).decode('utf-8')
                
                # Prepare the prompt for license plate extraction
                prompt = """Extract the Indian vehicle license plate number from the image. 
                Return only the license plate number in the format XX00XX0000. 
                If multiple plates are visible, return the most prominent one. 
                If no license plate is found, return 'NOT_FOUND'."""
                
                # Prepare the payload for Ollama API with memory optimization
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_data]
                        }
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,   # Low temperature for consistent results
                        "num_ctx": 256,       # Further reduce context size to save memory
                        "num_predict": 16,    # Limit prediction length
                        "low_vram": True,     # Enable low VRAM mode
                        "repeat_penalty": 1.2, # Reduce repetition
                        "top_k": 20,          # Limit vocabulary
                        "top_p": 0.9,         # Nucleus sampling
                        "mirostat": 1,        # Use Mirostat sampling
                        "mirostat_tau": 5.0,  # Mirostat tau parameter
                        "mirostat_eta": 0.1   # Mirostat eta parameter
                    }
                }
                
                # Make request to Ollama API
                response = requests.post(
                    f"{self.ollama_host}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=15  # 15 seconds timeout for image processing
                )
                
                # Check if request was successful
                if response.status_code != 200:
                    error_msg = response.text
                    logger.error(f"Ollama API request failed with status {response.status_code}: {error_msg}")
                    # Handle memory issues specifically
                    if "memory" in error_msg.lower() or "available" in error_msg.lower():
                        logger.error("Memory issue detected with Ollama model. Consider using a smaller model or increasing system memory.")
                        # For memory issues, don't retry to prevent resource exhaustion
                        max_memory_retries = 0  # No retries for memory issues
                        if attempt < min(max_retries - 1, max_memory_retries):
                            wait_time = (2 ** attempt) * 10  # Even more aggressive backoff for memory issues
                            logger.info(f"Waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                            continue
                    return "ERROR_PROCESSING"
                
                # Parse the response
                response_data = response.json()
                license_plate = response_data.get("message", {}).get("content", "").strip()
                
                # Validate the extracted license plate
                if not license_plate or license_plate == "NOT_FOUND":
                    return "NOT_FOUND"
                
                # Validate and clean the result
                validation_result = validate_license_plate(license_plate)
                if validation_result != 'invalid' and validation_result != 'invalid_state' and validation_result != 'invalid_bh_letters':
                    return {'plate': license_plate, 'valid': True, 'type': validation_result}
                else:
                    return {'plate': self._clean_license_plate(license_plate), 'valid': False, 'type': validation_result}
                    
            except Exception as e:
                logger.error(f"Error extracting license plate (attempt {attempt + 1}/{max_retries}): {str(e)}")
                # Be more conservative with retries to prevent resource exhaustion
                max_general_retries = 0  # No retries for general errors
                if attempt < min(max_retries - 1, max_general_retries):
                    wait_time = (2 ** attempt) * 5  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    return "PROCESSING_ERROR"
        
        return "PROCESSING_ERROR"
    
    def _clean_license_plate(self, plate_text):
        """
        Clean and validate the extracted license plate text
        
        Args:
            plate_text (str): Raw text extracted from the model
            
        Returns:
            str: Cleaned license plate or the original if cleaning not needed
        """
        # Remove common prefixes/suffixes that the model might add
        cleaned = plate_text.replace("License Plate:", "").replace("Plate:", "").strip()
        cleaned = cleaned.replace("Registration Number:", "").strip()
        
        # If the cleaned text looks like a valid Indian license plate, return it
        # Indian license plates typically have 2 letters, 2 digits, 2 letters, 4 digits
        # But there are variations, so we'll just return the cleaned text
        return cleaned
    
    def extract_with_comparison(self, image_bytes, image_path=None):
        """
        Run both Ollama and LlamaCPP in parallel and compare performance
        
        Args:
            image_bytes: Image data as bytes
            image_path: Path to image file (required for LlamaCPP)
            
        Returns:
            dict: Results from both engines with timing information
        """
        import threading
        import time
        
        results = {
            'ollama': None,
            'llamacpp': None,
            'winner': None,
            'speedup': 0
        }
        
        def run_ollama():
            start = time.time()
            try:
                result = self._extract_with_local_api(image_bytes)
                duration = time.time() - start
                results['ollama'] = {
                    'result': result,
                    'duration': duration,
                    'success': result not in ['ERROR_PROCESSING', 'PROCESSING_ERROR', 'NOT_FOUND']
                }
                logger.info(f"⚡ Ollama completed in {duration:.2f}s")
            except Exception as e:
                results['ollama'] = {'error': str(e), 'duration': time.time() - start, 'success': False}
        
        def run_llamacpp():
            if not self.llamacpp_service or not self.llamacpp_service.is_available():
                results['llamacpp'] = {'error': 'Not available', 'duration': 0, 'success': False}
                return
            
            if not image_path:
                results['llamacpp'] = {'error': 'No image path provided', 'duration': 0, 'success': False}
                return
            
            start = time.time()
            try:
                result = self.llamacpp_service.extract_license_plate(image_path)
                duration = time.time() - start
                results['llamacpp'] = {
                    'result': result,
                    'duration': duration,
                    'success': result is not None
                }
                logger.info(f"⚡ LlamaCPP completed in {duration:.2f}s")
            except Exception as e:
                results['llamacpp'] = {'error': str(e), 'duration': time.time() - start, 'success': False}
        
        # Run both in parallel
        t1 = threading.Thread(target=run_ollama)
        t2 = threading.Thread(target=run_llamacpp)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Determine winner
        ollama_time = results['ollama']['duration'] if results['ollama'] and results['ollama'].get('success') else float('inf')
        llamacpp_time = results['llamacpp']['duration'] if results['llamacpp'] and results['llamacpp'].get('success') else float('inf')
        
        if ollama_time < llamacpp_time:
            results['winner'] = 'ollama'
            results['speedup'] = llamacpp_time / ollama_time if ollama_time > 0 else 0
            logger.info(f"🏆 Ollama is {results['speedup']:.2f}x faster!")
        elif llamacpp_time < ollama_time:
            results['winner'] = 'llamacpp'
            results['speedup'] = ollama_time / llamacpp_time if llamacpp_time > 0 else 0
            logger.info(f"🏆 LlamaCPP is {results['speedup']:.2f}x faster!")
        else:
            results['winner'] = 'tie'
            results['speedup'] = 1.0
        
        logger.info(f"📊 Ollama: {ollama_time:.2f}s | LlamaCPP: {llamacpp_time:.2f}s")
        
        return results