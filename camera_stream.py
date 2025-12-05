import cv2
import os
from flask import Flask, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
RTSP_URL = os.getenv("RTSP_URL")

# Dummy camera for fallback
class DummyVideoCapture:
    def __init__(self):
        self.frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "No Camera Found", (180, 180), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    def isOpened(self):
        return True
    
    def read(self):
        time.sleep(0.1) # Simulate 10 FPS
        return True, self.frame.copy()
    
    def release(self):
        pass

def generate_frames():
    source = RTSP_URL
    cap = None
    
    if source:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            cap = None
            
    # No webcam fallback - only use RTSP or dummy camera
    if cap is None:
        cap = DummyVideoCapture()
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)