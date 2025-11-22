#!/usr/bin/env python3
"""
Simple test to verify LlamaCPP service fix
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

def test_llamacpp_fix():
    """Test that the LlamaCPP service fix works"""
    try:
        from services.llamacpp_service import LlamaCPPService
        
        logger.info("Initializing LlamaCPP service...")
        service = LlamaCPPService()
        
        logger.info(f"Service enabled: {service.enabled}")
        logger.info(f"Service available: {service.is_available()}")
        
        if not service.is_available():
            logger.error("LlamaCPP service is not available")
            return False
            
        # Test with a simple command to see if the argument issue is fixed
        import subprocess
        
        # Build the same command that the service would use
        cmd = [
            service.llama_cli_path,
            "-m", service.model_path,
            "--mmproj", service.mmproj_path,
            "--help"
        ]
        
        logger.info(f"Testing command: {' '.join(cmd)}")
        
        # Run a quick help command to verify arguments are valid
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            logger.info("Command executed successfully - LlamaCPP arguments are valid!")
            return True
        else:
            logger.error(f"Command failed with return code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error testing LlamaCPP fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Testing LlamaCPP service fix...")
    
    success = test_llamacpp_fix()
    
    if success:
        logger.info("✅ LlamaCPP service fix verified!")
        sys.exit(0)
    else:
        logger.error("❌ LlamaCPP service fix failed!")
        sys.exit(1)