#!/usr/bin/env python3
"""
Test script for PaliGemma model with llama-cpp-python
"""
import os
import sys

# Test if llama-cpp-python is installed
try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import MoondreamChatHandler
    print("✓ llama-cpp-python is installed")
except ImportError:
    print("✗ llama-cpp-python not found")
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
if not os.path.exists(MODEL_PATH):
    print(f"✗ Model file not found: {MODEL_PATH}")
    sys.exit(1)

if not os.path.exists(MMPROJ_PATH):
    print(f"✗ MMProj file not found: {MMPROJ_PATH}")
    sys.exit(1)

if not os.path.exists(IMAGE_PATH):
    print(f"✗ Image file not found: {IMAGE_PATH}")
    sys.exit(1)

print("\n✓ All files found")

try:
    print("\nLoading model...")
    
    # Try loading with basic configuration
    llm = Llama(
        model_path=MODEL_PATH,
        chat_format="gemma",
        n_ctx=2048,
        n_threads=4,
        n_gpu_layers=0,  # CPU only
        verbose=True
    )
    
    print("✓ Model loaded successfully!")
    
    # Test simple text generation
    print("\nTesting text generation...")
    response = llm.create_completion(
        "Hello, this is a test.",
        max_tokens=32,
        temperature=0.1
    )
    print(f"Response: {response['choices'][0]['text']}")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
