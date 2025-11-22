#!/usr/bin/env python3
"""
Test to demonstrate the optimized LlamaCPP performance
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

def test_optimized_performance():
    """Test the optimized LlamaCPP performance"""
    try:
        from services.llamacpp_service import LlamaCPPService
        
        logger.info("Testing optimized LlamaCPP service...")
        service = LlamaCPPService()
        
        logger.info(f"Threads: {service.threads}")
        logger.info(f"Context Size: {service.ctx_size}")
        logger.info(f"Cache Enabled: {service.cache_enabled}")
        
        # Check if service is available
        if not service.is_available():
            logger.error("LlamaCPP service is not available")
            return False
            
        # Test with real image
        test_image_path = "test_plate.jpg"
        if not os.path.exists(test_image_path):
            logger.error(f"Test image not found: {test_image_path}")
            return False
            
        logger.info(f"Testing with image: {test_image_path}")
        
        # First run (cold start)
        logger.info("=== FIRST RUN (Cold Start) ===")
        start_time = time.time()
        result = service.extract_license_plate(test_image_path)
        first_run_time = time.time() - start_time
        logger.info(f"First run time: {first_run_time:.2f} seconds")
        logger.info(f"Result: {result}")
        
        # Second run (warm cache)
        logger.info("=== SECOND RUN (Warm Cache) ===")
        start_time = time.time()
        result = service.extract_license_plate(test_image_path)
        second_run_time = time.time() - start_time
        logger.info(f"Second run time: {second_run_time:.2f} seconds")
        logger.info(f"Result: {result}")
        
        # Performance improvement
        if first_run_time > 0 and second_run_time > 0:
            improvement = first_run_time / second_run_time
            logger.info(f"Performance improvement: {improvement:.2f}x faster on second run")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing optimized performance: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting optimized LlamaCPP performance test...")
    test_optimized_performance()
    logger.info("Optimized performance test completed.")