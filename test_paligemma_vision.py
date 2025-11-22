#!/usr/bin/env python3
"""
Test script for PaliGemma vision model with llama-cpp-python
Tests license plate detection with vision capabilities
"""
import os
import sys

# Test if llama-cpp-python is installed
try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Llava15ChatHandler
    print("✓ llama-cpp-python is installed")
except ImportError as e:
    print(f"✗ llama-cpp-python not found: {e}")
    print("Installing llama-cpp-python...")
    os.system("pip install llama-cpp-python")
    sys.exit(1)

# Paths
MODEL_PATH = "llama.cpp/models/paligemma/paligemma-3b-mix-224-text-model-q4_k_m.gguf"
MMPROJ_PATH = "llama.cpp/models/paligemma/paligemma-3b-mix-224-mmproj-f16.gguf"
IMAGE_PATH = "test_plate.jpg"

print(f"\nModel: {MODEL_PATH}")
print(f"MMProj: {MMPROJ_PATH}")
print(f"Image: {IMAGE_PATH}")

# Check if files exist
for path, name in [(MODEL_PATH, "Model"), (MMPROJ_PATH, "MMProj"), (IMAGE_PATH, "Image")]:
    if not os.path.exists(path):
        print(f"✗ {name} file not found: {path}")
        sys.exit(1)
    print(f"✓ {name} file found")

try:
    print("\n" + "="*60)
    print("Loading PaliGemma vision model...")
    print("="*60)
    
    # Initialize chat handler with vision support
    chat_handler = Llava15ChatHandler(clip_model_path=MMPROJ_PATH)
    
    # Load the model with vision support
    llm = Llama(
        model_path=MODEL_PATH,
        chat_handler=chat_handler,
        n_ctx=2048,
        n_threads=4,
        n_gpu_layers=0,  # CPU only
        logits_all=True,
        verbose=True
    )
    
    print("\n✓ Model loaded successfully with vision support!")
    
    # Test vision inference
    print("\n" + "="*60)
    print("Testing license plate detection...")
    print("="*60)
    
    response = llm.create_chat_completion(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"file://{os.path.abspath(IMAGE_PATH)}"}},
                    {"type": "text", "text": "detect license plate"}
                ]
            }
        ],
        max_tokens=64,
        temperature=0.1
    )
    
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    result_text = response['choices'][0]['message']['content']
    print(f"License Plate Detection: {result_text}")
    print("="*60)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    
    # Try alternative approach
    print("\n" + "="*60)
    print("Trying alternative vision integration method...")
    print("="*60)
    
    try:
        # Load model without chat handler first
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0,
            verbose=False
        )
        
        # Try simple completion with image token
        prompt = "<image>detect license plate"
        response = llm.create_completion(
            prompt,
            max_tokens=64,
            temperature=0.1
        )
        
        print(f"\nAlternative result: {response['choices'][0]['text']}")
        
    except Exception as e2:
        print(f"Alternative method also failed: {e2}")
