#!/usr/bin/env python3
"""
Direct test of LlamaCPP service with test image
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_direct_llamacpp():
    """Test LlamaCPP service directly with test image"""
    try:
        from services.llamacpp_service import LlamaCPPService
        
        logger.info("Initializing LlamaCPP service...")
        service = LlamaCPPService()
        
        # Check if service is available
        if not service.is_available():
            logger.error("LlamaCPP service is not available")
            return False
            
        logger.info("LlamaCPP service is available")
        logger.info(f"CLI path: {service.llama_cli_path}")
        logger.info(f"Model path: {service.model_path}")
        logger.info(f"Mmproj path: {service.mmproj_path}")
        
        # Test with real image
        test_image_path = "test_plate.jpg"
        if not os.path.exists(test_image_path):
            logger.error(f"Test image not found: {test_image_path}")
            return False
            
        logger.info(f"Testing with image: {test_image_path}")
        
        # Process the image
        result = service.extract_license_plate(test_image_path)
        
        logger.info("=== RESULT ===")
        if result:
            logger.info(f"✅ Success! Extracted license plate: {result}")
        else:
            logger.info("❌ Failed to extract license plate")
            logger.info("This could be due to:")
            logger.info("  1. Image quality issues")
            logger.info("  2. Model not recognizing the license plate format")
            logger.info("  3. Processing timeout")
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing LlamaCPP service: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting direct LlamaCPP test...")
    test_direct_llamacpp()
    logger.info("Direct LlamaCPP test completed.")