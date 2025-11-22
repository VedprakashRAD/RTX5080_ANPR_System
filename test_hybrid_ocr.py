import logging
import time
import os
from services.hybrid_ocr_service import HybridOCRService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hybrid_ocr():
    print("=== Testing Hybrid OCR Strategy (Doctr + SmolVLM2) ===")
    
    image_path = "test_plate.jpg"
    if not os.path.exists(image_path):
        print(f"❌ Test image not found: {image_path}")
        return

    print("Initializing HybridOCRService...")
    start_init = time.time()
    service = HybridOCRService()
    print(f"✅ Service initialized in {time.time() - start_init:.2f}s")

    print(f"\nProcessing image: {image_path}")
    start_time = time.time()
    
    # Run extraction
    result = service.extract_license_plate(image_path)
    
    duration = time.time() - start_time
    print(f"\n=== Result ===")
    print(f"Plate: {result}")
    print(f"Time:  {duration:.2f}s")
    
    if duration < 1.0:
        print("🚀 Speed: EXTREMELY FAST (< 1s)")
    elif duration < 3.0:
        print("⚡ Speed: FAST (< 3s)")
    else:
        print("🐢 Speed: SLOW (Fallback used?)")

if __name__ == "__main__":
    test_hybrid_ocr()
