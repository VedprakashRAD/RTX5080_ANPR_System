#!/usr/bin/env python3
"""
Debug script to test LlamaCPP integration in the license plate service
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_license_plate_service_with_llamacpp():
    """Test the license plate service with LlamaCPP specifically"""
    try:
        from services.license_plate_service import LicensePlateService
        
        logger.info("Initializing LicensePlateService...")
        service = LicensePlateService()
        
        logger.info(f"LlamaCPP service available: {service.llamacpp_service is not None}")
        if service.llamacpp_service:
            logger.info(f"LlamaCPP service enabled: {service.llamacpp_service.enabled}")
            logger.info(f"LlamaCPP service available: {service.llamacpp_service.is_available()}")
        
        # Check if comparison mode is enabled
        logger.info(f"Comparison mode enabled: {service.compare_engines}")
        
        # Try to load a test image
        test_image_path = "test_plate.jpg"
        if os.path.exists(test_image_path):
            logger.info(f"Testing with image: {test_image_path}")
            with open(test_image_path, 'rb') as f:
                image_bytes = f.read()
            
            # Test direct LlamaCPP call if available
            if service.llamacpp_service and service.llamacpp_service.is_available():
                logger.info("Testing direct LlamaCPP call...")
                result = service.llamacpp_service.extract_with_timing(test_image_path)
                logger.info(f"LlamaCPP result: {result}")
            else:
                logger.warning("LlamaCPP service not available for direct testing")
            
            # Test comparison mode if enabled
            if service.compare_engines:
                logger.info("Testing comparison mode...")
                result = service.extract_with_comparison(image_bytes, test_image_path)
                logger.info(f"Comparison result: {result}")
            else:
                logger.info("Comparison mode not enabled")
                
        else:
            logger.warning(f"Test image not found: {test_image_path}")
            logger.info("Available files in directory:")
            for f in os.listdir('.'):
                logger.info(f"  {f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing license plate service: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting LlamaCPP integration diagnostics...")
    
    success = test_license_plate_service_with_llamacpp()
    
    if success:
        logger.info("LlamaCPP integration test completed.")
    else:
        logger.error("LlamaCPP integration test failed.")
        sys.exit(1)