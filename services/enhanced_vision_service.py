"""
Enhanced Vision Service for Vehicle Metadata Extraction

Extracts:
- License plate number
- Vehicle make (Toyota, Honda, etc.)
- Vehicle model (Fortuner, City, etc.)
- Vehicle color (White, Red, etc.)
- Vehicle type (CAR, SUV, TRUCK, etc.)
"""

import requests
import json
import os
from typing import Dict, Optional
import base64

class EnhancedVisionService:
    """Enhanced vision LLM service for vehicle metadata extraction"""
    
    def __init__(self):
        """Initialize vision service"""
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")
        
        # Strict prompt to force JSON output only
        self.prompt_template = """You are a vehicle data extraction system. Analyze the image and return ONLY a JSON object with this exact format:

{"plate":"LICENSE_PLATE","type":"VEHICLE_TYPE","color":"COLOR"}

Rules:
- plate: Indian license plate number (e.g., "KL 34E 952") or null if not visible
- type: Must be one of: CAR, BIKE, SCOOTER, BUS, TRUCK
- color: Vehicle color (e.g., "black", "white", "red")

IMPORTANT: Return ONLY the JSON object, no explanations or additional text."""
    
    def _resize_for_speed(self, image_path: str) -> str:
        """Resize image to 560x560 for maximum speed (50% speed gain)"""
        import cv2
        import tempfile
        
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return image_path
            
            # Resize to smaller size for maximum speed (40-50% faster)
            img_resized = cv2.resize(img, (384, 384))
            
            # Save to temp file
            temp_path = tempfile.mktemp(suffix='.jpg')
            cv2.imwrite(temp_path, img_resized)
            
            return temp_path
        except Exception as e:
            print(f"⚠️ Resize failed: {e}, using original")
            return image_path
    
    def extract_vehicle_metadata(self, image_path: str) -> Dict:
        """
        Extract vehicle metadata from image
        
        Args:
            image_path: Path to vehicle image
        
        Returns:
            {
                'success': bool,
                'plate': str,
                'vehicle': {
                    'make': str,
                    'model': str,
                    'color': str,
                    'type': str
                },
                'confidence': float,
                'raw_response': str
            }
        """
        try:
            # Resize for speed
            resized_path = self._resize_for_speed(image_path)
            
            # Encode image to base64
            with open(resized_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Clean up temp file
            if resized_path != image_path and os.path.exists(resized_path):
                os.remove(resized_path)
            
            # Prepare optimized API request
            payload = {
                "model": self.model,
                "prompt": self.prompt_template,
                "images": [image_data],
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 64,
                    "num_gpu": 999,
                    "num_thread": 8
                }
            }
            
            # Call Ollama API
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                return self._error_response(f"API error: {response.status_code}")
            
            result = response.json()
            raw_text = result.get('response', '')
            
            # Debug: Print raw response to see what Ollama is returning
            print(f"🔍 Ollama raw response: {raw_text[:200]}...")  # First 200 chars
            
            # Parse JSON response
            parsed_data = self._parse_response(raw_text)
            
            if not parsed_data:
                print(f"❌ Failed to parse Ollama response: {raw_text}")
                return self._error_response(f"Failed to parse response: {raw_text[:100]}")
            
            # Calculate confidence
            confidence = self._calculate_confidence(parsed_data)
            
            return {
                'success': True,
                'plate': parsed_data.get('plate'),
                'vehicle': {
                    'make': parsed_data.get('make'),
                    'model': parsed_data.get('model'),
                    'color': parsed_data.get('color', 'UNKNOWN'),
                    'type': parsed_data.get('type', 'UNKNOWN')
                },
                'confidence': confidence,
                'raw_response': raw_text
            }
            
        except requests.exceptions.Timeout:
            return self._error_response("Request timeout")
        except Exception as e:
            return self._error_response(f"Error: {str(e)}")
    
    def _parse_response(self, raw_text: str) -> Optional[Dict]:
        """
        Parse JSON response from LLM
        
        Handles:
        - Clean JSON
        - JSON wrapped in markdown code blocks
        - Malformed JSON
        """
        try:
            # Try direct JSON parse
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        if "```json" in raw_text:
            try:
                start = raw_text.find("```json") + 7
                end = raw_text.find("```", start)
                json_str = raw_text[start:end].strip()
                return json.loads(json_str)
            except:
                pass
        
        # Try extracting JSON from curly braces
        if "{" in raw_text and "}" in raw_text:
            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                json_str = raw_text[start:end]
                return json.loads(json_str)
            except:
                pass
        
        return None
    
    def _calculate_confidence(self, data: Dict) -> float:
        """
        Calculate confidence score based on completeness
        
        Logic:
        - All fields detected: 0.95
        - 4 fields detected: 0.85
        - 3 fields detected: 0.70
        - 2 fields detected: 0.50
        - 1 field detected: 0.30
        """
        fields = ['plate', 'make', 'model', 'color', 'type']
        detected = sum(1 for field in fields if data.get(field, 'UNKNOWN') != 'UNKNOWN')
        
        confidence_map = {
            5: 0.95,
            4: 0.85,
            3: 0.70,
            2: 0.50,
            1: 0.30,
            0: 0.10
        }
        
        return confidence_map.get(detected, 0.10)
    
    def _error_response(self, error_msg: str) -> Dict:
        """Return error response"""
        return {
            'success': False,
            'plate': 'ERROR',
            'vehicle': {
                'make': 'UNKNOWN',
                'model': 'UNKNOWN',
                'color': 'UNKNOWN',
                'type': 'UNKNOWN'
            },
            'confidence': 0.0,
            'error': error_msg
        }
