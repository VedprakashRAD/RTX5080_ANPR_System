#!/usr/bin/env python3
"""
Debug script to test Ollama API directly
"""

import requests
import base64
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def read_image_as_base64(image_path):
    """
    Read image file and convert to base64
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Base64 encoded image data or None if failed
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error reading image: {str(e)}")
        return None

def test_ollama_api():
    """
    Test Ollama API directly with base64 image data
    """
    # Test with a local image file
    image_path = "test_plate.jpg"
    
    # Read and convert to base64
    image_data = read_image_as_base64(image_path)
    if not image_data:
        print("Failed to read image")
        return
    
    print(f"Image data length: {len(image_data)}")
    print(f"First 100 chars: {image_data[:100]}")
    
    # Ollama configuration
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name = os.getenv("MODEL_NAME", "qwen2.5vl:3b")
    
    # Prepare the prompt for license plate extraction
    prompt = """Extract the Indian vehicle license plate number from the image. 
    Return only the license plate number in the format XX00XX0000. 
    If multiple plates are visible, return the most prominent one. 
    If no license plate is found, return 'NOT_FOUND'."""
    
    # Prepare the payload for Ollama API
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_data]
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1  # Low temperature for consistent results
        }
    }
    
    print(f"Sending request to {ollama_host}/api/chat")
    print(f"Model: {model_name}")
    
    # Make request to Ollama API
    try:
        response = requests.post(
            f"{ollama_host}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60  # 60 seconds timeout for image processing
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        
        # Check if request was successful
        if response.status_code != 200:
            print(f"Ollama API request failed with status {response.status_code}: {response.text}")
            return
        
        # Parse the response
        response_data = response.json()
        license_plate = response_data.get("message", {}).get("content", "").strip()
        print(f"Extracted license plate: {license_plate}")
        
    except Exception as e:
        print(f"Error contacting Ollama: {str(e)}")

if __name__ == "__main__":
    test_ollama_api()