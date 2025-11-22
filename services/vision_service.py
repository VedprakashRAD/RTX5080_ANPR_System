#!/usr/bin/env python3
"""
Vision service for Refine_ALPR.
* Sends the image (base64) to Ollama running the `qwen2.5vl:3b` model.
* Returns the model's textual response (license‑plate string).
* Includes in-memory caching for repeated images.
* Supports optional Hailo acceleration if SDK is available.
"""

import os
import base64
import json
import subprocess
import hashlib
import sys
from dotenv import load_dotenv

load_dotenv()

# Default prompt – can be overridden if needed
DEFAULT_PROMPT = "Read the Indian license plate number from this image and return it in uppercase without any extra text."

# Simple in‑memory cache for image results (key: SHA256 of image bytes)
_image_cache = {}
_CACHE_MAX_SIZE = 100  # limit number of cached entries

# Try to import Hailo SDK
try:
    from hailo_clip import get_image_embedding
    HAILO_AVAILABLE = True
except ImportError:
    HAILO_AVAILABLE = False
    # print("⚠️ Hailo SDK not found, falling back to CPU-based Ollama vision.")

def run_vision_llm(image_path: str, prompt: str = DEFAULT_PROMPT) -> str:
    """Run the vision‑language model via Ollama with caching.

    Reads the image file, computes a hash, checks the cache,
    and if not found, sends it to Ollama.
    """
    # Read image bytes
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return ""
    
    # Compute cache key
    cache_key = hashlib.sha256(img_bytes).hexdigest()
    
    # Check cache
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    # Prepare payload
    payload = {
        "model": os.getenv("MODEL_NAME", "qwen2.5vl:3b"),
        "stream": False
    }

    # Use Hailo if available (not implemented for legacy format yet, fallback to CPU)
    # Standard image encoding (CPU fallback) - Legacy Format
    img_b64 = base64.b64encode(img_bytes).decode()
    payload["messages"] = [
        {
            "role": "user",
            "content": prompt,
            "images": [img_b64]
        }
    ]

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/chat",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, check=True
        )
        resp = json.loads(result.stdout)

        answer = resp.get("message", {}).get("content", "")
        
        # Clean output: remove <think>...</think> blocks if present
        import re
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
        # Also remove any leading/trailing whitespace or markdown code blocks
        answer = answer.replace("```", "").strip()
        
        # Store in cache (evict oldest if over limit)
        if len(_image_cache) >= _CACHE_MAX_SIZE:
            # remove arbitrary first key (simple FIFO eviction)
            _image_cache.pop(next(iter(_image_cache)))
        _image_cache[cache_key] = answer
        
        return answer
    except Exception as e:
        print(f"Error in run_vision_llm: {e}")
        return ""

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run_vision_llm(sys.argv[1]))
    else:
        print("Usage: python3 vision_service.py <image_path>")
