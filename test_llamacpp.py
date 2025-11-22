#!/usr/bin/env python3
"""
Test script to diagnose LlamaCPP issues
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

def test_llamacpp_service():
    """Test the LlamaCPP service directly"""
    try:
        from services.llamacpp_service import LlamaCPPService
        
        logger.info("Initializing LlamaCPP service...")
        service = LlamaCPPService()
        
        logger.info(f"LlamaCPP enabled: {service.enabled}")
        logger.info(f"CLI path: {service.llama_cli_path}")
        logger.info(f"Model path: {service.model_path}")
        logger.info(f"Mmproj path: {service.mmproj_path}")
        
        # Check if service is available
        is_available = service.is_available()
        logger.info(f"Service available: {is_available}")
        
        if not is_available:
            logger.error("LlamaCPP service is not available. Checking individual components...")
            
            # Check if CLI exists
            if not os.path.exists(service.llama_cli_path):
                logger.error(f"CLI not found at: {service.llama_cli_path}")
            else:
                logger.info(f"CLI found at: {service.llama_cli_path}")
            
            # Check if model exists
            if not os.path.exists(service.model_path):
                logger.error(f"Model not found at: {service.model_path}")
            else:
                logger.info(f"Model found at: {service.model_path}")
                
            # Check if mmproj exists
            if not os.path.exists(service.mmproj_path):
                logger.error(f"Mmproj not found at: {service.mmproj_path}")
            else:
                logger.info(f"Mmproj found at: {service.mmproj_path}")
        
        return is_available
        
    except Exception as e:
        logger.error(f"Error initializing LlamaCPP service: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_cli():
    """Test the CLI directly"""
    try:
        import subprocess
        import time
        
        # Get paths from environment
        llama_cli_path = os.getenv("LLAMA_CLI_PATH", "./llama-llava-cli")
        model_path = os.getenv("LLAMA_MODEL_PATH", "./models/Qwen2-VL-2B-Instruct-Q2_K.gguf")
        mmproj_path = os.getenv("LLAMA_MMPROJ_PATH", "./models/mmproj-Qwen2-VL-2B-Instruct-f16.gguf")
        
        logger.info("Testing CLI directly...")
        logger.info(f"CLI path: {llama_cli_path}")
        logger.info(f"Model path: {model_path}")
        logger.info(f"Mmproj path: {mmproj_path}")
        
        # Check if files exist
        if not os.path.exists(llama_cli_path):
            logger.error(f"CLI not found at: {llama_cli_path}")
            return False
            
        if not os.path.exists(model_path):
            logger.error(f"Model not found at: {model_path}")
            return False
            
        if not os.path.exists(mmproj_path):
            logger.error(f"Mmproj not found at: {mmproj_path}")
            return False
            
        # Test with a simple command
        cmd = [
            llama_cli_path,
            "-m", model_path,
            "--mmproj", mmproj_path,
            "--help"
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("CLI test successful!")
            logger.debug(f"Output: {result.stdout[:500]}...")  # First 500 chars
            return True
        else:
            logger.error(f"CLI test failed with return code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("CLI test timeout")
        return False
    except Exception as e:
        logger.error(f"Error testing CLI directly: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting LlamaCPP diagnostics...")
    
    # Test service
    service_ok = test_llamacpp_service()
    
    # Test CLI directly
    cli_ok = test_direct_cli()
    
    logger.info(f"Service test: {'PASS' if service_ok else 'FAIL'}")
    logger.info(f"CLI test: {'PASS' if cli_ok else 'FAIL'}")
    
    if not service_ok and not cli_ok:
        logger.error("Both tests failed. LlamaCPP is not working.")
        sys.exit(1)
    elif service_ok and cli_ok:
        logger.info("All tests passed. LlamaCPP is working.")
        sys.exit(0)
    else:
        logger.warning("Some tests failed. Check logs for details.")
        sys.exit(1)