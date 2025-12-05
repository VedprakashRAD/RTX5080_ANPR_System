#!/bin/bash
# Start ANPR Camera Processor

cd /home/raai/development/ANPR/RTX5080_ALPR

# Default camera settings
CAMERA_ID="${1:-GATE1-ENTRY}"
RTSP_URL="${2:-rtsp://admin:Rasdf_1212@10.1.2.201:554/stream1}"

echo "🎥 Starting Camera Processor..."
echo "📹 Camera ID: $CAMERA_ID"
echo "📡 RTSP URL: $RTSP_URL"
echo ""

python3 smart_vehicle_detector.py "$CAMERA_ID" "$RTSP_URL"
