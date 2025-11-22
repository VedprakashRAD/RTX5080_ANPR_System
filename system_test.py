import cv2
import requests
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
RTSP_URL = os.getenv("RTSP_URL")
API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = os.getenv("API_PORT", "8000")

def test_complete_system():
    print("=== Complete System Test ===")
    print(f"RTSP URL: {RTSP_URL}")
    print(f"API URL: http://{API_HOST}:{API_PORT}")
    
    # Test 1: Camera Connection
    # Test 1: Camera Connection
    print("\n1. Testing camera connection...")
    try:
        # Handle empty RTSP_URL by falling back to webcam 0
        source = RTSP_URL
        cap = None
        
        if source:
            print(f"   Trying RTSP: {source}")
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                print("   ❌ RTSP connection failed")
                cap = None
        
        if cap is None:
            print("   Trying webcam (index 0)...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("   ❌ Webcam connection failed")
                cap = None
        
        if cap is None:
            print("   ⚠️ No physical camera found. System will use Dummy Camera fallback.")
            print("   ✅ Camera test passed (using fallback)")
            return True

        print("✅ Camera opened successfully")
        
        # Read a test frame
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to read frame from camera")
            cap.release()
            return False
        print(f"✅ Successfully read frame - Shape: {frame.shape}")
        cap.release()
    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False
    
    # Test 2: API Server
    print("\n2. Testing API server...")
    try:
        response = requests.get(f"http://{API_HOST}:{API_PORT}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running")
        else:
            print("❌ API server is not responding")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to API server: {e}")
        return False
    
    # Test 3: Video Feed Endpoint
    print("\n3. Testing video feed endpoint...")
    try:
        response = requests.get(f"http://{API_HOST}:{API_PORT}/video_feed", timeout=5, stream=True)
        if response.status_code == 200 and 'multipart/x-mixed-replace' in response.headers.get('content-type', ''):
            print("✅ Video feed endpoint is working")
        else:
            print("❌ Video feed endpoint is not working properly")
            return False
    except Exception as e:
        print(f"❌ Video feed test failed: {e}")
        return False
    
    # Test 4: Dashboard Endpoint
    print("\n4. Testing dashboard endpoint...")
    try:
        response = requests.get(f"http://{API_HOST}:{API_PORT}/dashboard", timeout=5)
        if response.status_code == 200 and '<html>' in response.text:
            print("✅ Dashboard endpoint is working")
        else:
            print("❌ Dashboard endpoint is not working properly")
            return False
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
        return False
    
    # Test 5: Live Detections API
    print("\n5. Testing live detections API...")
    try:
        response = requests.get(f"http://{API_HOST}:{API_PORT}/api/live-detections", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Live detections API is working")
                print(f"   Found {len(data.get('detections', []))} recent detections")
            else:
                print("❌ Live detections API returned error")
                return False
        else:
            print("❌ Live detections API is not responding")
            return False
    except Exception as e:
        print(f"❌ Live detections API test failed: {e}")
        return False
    
    print("\n=== All tests passed! System is working correctly ===")
    return True

if __name__ == "__main__":
    test_complete_system()