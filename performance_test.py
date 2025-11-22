#!/usr/bin/env python3
"""
Performance test for LlamaCPP with real image
"""
import os
import sys
import time
import logging
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llamacpp_performance():
    """Test LlamaCPP performance with real image"""
    try:
        from services.llamacpp_service import LlamaCPPService
        
        logger.info("Initializing LlamaCPP service...")
        service = LlamaCPPService()
        
        # Check if service is available
        if not service.is_available():
            logger.error("LlamaCPP service is not available")
            return False
            
        logger.info("LlamaCPP service is available")
        
        # Test with real image
        test_image_path = "test_plate.jpg"
        if not os.path.exists(test_image_path):
            logger.error(f"Test image not found: {test_image_path}")
            # List available images
            logger.info("Available files in directory:")
            for f in os.listdir('.'):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    logger.info(f"  {f}")
            return False
            
        logger.info(f"Testing with image: {test_image_path}")
        
        # Measure performance
        start_time = time.time()
        result = service.extract_with_timing(test_image_path)
        end_time = time.time()
        
        total_time = end_time - start_time
        processing_time = result.get('duration', 0)
        success = result.get('success', False)
        text = result.get('text', None)
        
        logger.info("=== PERFORMANCE RESULTS ===")
        logger.info(f"Total time (including overhead): {total_time:.2f} seconds")
        logger.info(f"Processing time (model only): {processing_time:.2f} seconds")
        logger.info(f"Success: {success}")
        logger.info(f"Result: {text}")
        
        if success:
            logger.info("✅ LlamaCPP successfully processed the image")
        else:
            logger.info("❌ LlamaCPP failed to process the image")
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing LlamaCPP performance: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comparison_mode():
    """Test comparison mode between Ollama and LlamaCPP"""
    try:
        from services.license_plate_service import LicensePlateService
        
        logger.info("Initializing LicensePlateService...")
        service = LicensePlateService()
        
        # Check if comparison mode is enabled
        if not service.compare_engines:
            logger.info("Comparison mode is not enabled")
            return False
            
        logger.info("Comparison mode is enabled")
        
        # Test with real image
        test_image_path = "test_plate.jpg"
        if not os.path.exists(test_image_path):
            logger.error(f"Test image not found: {test_image_path}")
            return False
            
        logger.info(f"Testing comparison mode with image: {test_image_path}")
        
        # Read image bytes
        with open(test_image_path, 'rb') as f:
            image_bytes = f.read()
        
        # Measure performance
        start_time = time.time()
        result = service.extract_with_comparison(image_bytes, test_image_path)
        end_time = time.time()
        
        total_time = end_time - start_time
        
        logger.info("=== COMPARISON RESULTS ===")
        logger.info(f"Total time: {total_time:.2f} seconds")
        
        # Ollama results
        ollama_result = result.get('ollama', {})
        ollama_success = ollama_result.get('success', False)
        ollama_time = ollama_result.get('duration', 0)
        ollama_text = ollama_result.get('result', None)
        
        logger.info(f"Ollama - Time: {ollama_time:.2f}s, Success: {ollama_success}, Result: {ollama_text}")
        
        # LlamaCPP results
        llamacpp_result = result.get('llamacpp', {})
        llamacpp_success = llamacpp_result.get('success', False)
        llamacpp_time = llamacpp_result.get('duration', 0)
        llamacpp_text = llamacpp_result.get('result', None)
        
        logger.info(f"LlamaCPP - Time: {llamacpp_time:.2f}s, Success: {llamacpp_success}, Result: {llamacpp_text}")
        
        # Winner
        winner = result.get('winner', 'unknown')
        speedup = result.get('speedup', 0)
        
        logger.info(f"Winner: {winner}")
        if speedup > 0:
            logger.info(f"Speedup: {speedup:.2f}x")
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing comparison mode: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting LlamaCPP performance test...")
    
    # Test individual LlamaCPP performance
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Individual LlamaCPP Performance")
    logger.info("="*50)
    test_llamacpp_performance()
    
    # Test comparison mode
    logger.info("\n" + "="*50)
    logger.info("TEST 2: Comparison Mode (Ollama vs LlamaCPP)")
    logger.info("="*50)
    test_comparison_mode()
    
    logger.info("\nPerformance test completed.")