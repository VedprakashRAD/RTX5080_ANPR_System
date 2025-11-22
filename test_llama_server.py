import logging
import time
import os
from services.llama_server_service import LlamaServerService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_llama_server():
    print("=== Testing Persistent LlamaServer Strategy ===")
    
    image_path = "test_plate.jpg"
    if not os.path.exists(image_path):
        print(f"❌ Test image not found: {image_path}")
        return

    print("Initializing LlamaServerService (may take time to start server)...")
    start_init = time.time()
    service = LlamaServerService()
    print(f"✅ Service initialized in {time.time() - start_init:.2f}s")

    print(f"\nProcessing image: {image_path}")
    
    # First Run (Warmup)
    print("--- Run 1 (Warmup) ---")
    start_time = time.time()
    result1 = service.extract_license_plate(image_path)
    duration1 = time.time() - start_time
    print(f"Result: {result1}")
    print(f"Time:   {duration1:.2f}s")
    
    # Second Run (Performance Test)
    print("\n--- Run 2 (Performance) ---")
    start_time = time.time()
    result2 = service.extract_license_plate(image_path)
    duration2 = time.time() - start_time
    print(f"Result: {result2}")
    print(f"Time:   {duration2:.2f}s")
    
    print("\n=== Performance Summary ===")
    print(f"Warmup Time:      {duration1:.2f}s")
    print(f"Inference Time:   {duration2:.2f}s")
    
    if duration2 < 10.0:
        print("🚀 Speed: EXCELLENT (< 10s)")
    elif duration2 < 15.0:
        print("⚡ Speed: GOOD (< 15s)")
    else:
        print("🐢 Speed: SLOW (> 15s)")

if __name__ == "__main__":
    test_llama_server()
