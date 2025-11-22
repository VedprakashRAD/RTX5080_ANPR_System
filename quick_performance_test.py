#!/usr/bin/env python3
"""
Quick performance test for LlamaCPP CLI with real image
"""
import os
import sys
import time
import subprocess
import logging
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llamacpp_cli_performance():
    """Test LlamaCPP CLI performance directly"""
    try:
        # Get paths from environment
        llama_cli_path = os.getenv("LLAMA_CLI_PATH", "/home/raai/development/Refine_ALPR/llama.cpp/build/bin/llama-mtmd-cli")
        model_path = os.getenv("LLAMA_MODEL_PATH", "/home/raai/development/Refine_ALPR/llama.cpp/models/qwen2-vl/qwen2-vl-2b-instruct-q2_k.gguf")
        mmproj_path = os.getenv("LLAMA_MMPROJ_PATH", "/home/raai/development/Refine_ALPR/llama.cpp/models/qwen2-vl/mmproj-qwen2-vl-2b-instruct-f16.gguf")
        
        test_image_path = "test_plate.jpg"
        
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
            
        if not os.path.exists(test_image_path):
            logger.error(f"Test image not found: {test_image_path}")
            return False
            
        logger.info("Testing LlamaCPP CLI performance directly...")
        logger.info(f"CLI path: {llama_cli_path}")
        logger.info(f"Model path: {model_path}")
        logger.info(f"Mmproj path: {mmproj_path}")
        logger.info(f"Image path: {test_image_path}")
        
        # Build command
        cmd = [
            llama_cli_path,
            "-m", model_path,
            "--mmproj", mmproj_path,
            "--image", test_image_path,
            "-p", "Extract the Indian vehicle license plate number from the image. Return only the license plate number in the format XX00XX0000. If no license plate is found, return 'NOT_FOUND'.",
            "--temp", "0.1",
            "--top-k", "1",
            "-n", "32"
        ]
        
        logger.info(f"Running command: {' '.join(cmd[:5])} ...")
        
        # Measure execution time
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45  # 45 second timeout
            )
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            logger.info("=== CLI PERFORMANCE RESULTS ===")
            logger.info(f"Execution time: {execution_time:.2f} seconds")
            logger.info(f"Return code: {result.returncode}")
            
            if result.returncode == 0:
                output = result.stdout.strip()
                logger.info(f"Output: {output}")
                logger.info("✅ CLI executed successfully")
            else:
                logger.error(f"CLI failed with return code {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(f"CLI timed out after {execution_time:.2f} seconds")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing LlamaCPP CLI performance: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting quick LlamaCPP performance test...")
    test_llamacpp_cli_performance()
    logger.info("Quick performance test completed.")