#!/bin/bash
# Start ANPR API Server

cd /home/raai/development/ANPR/RTX5080_ALPR

# Suppress OpenCV warnings
export OPENCV_LOG_LEVEL=ERROR
export OPENCV_VIDEOIO_DEBUG=0

echo "🚀 Starting ANPR API Server..."
echo "📡 API will be available at: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""

python3 app.py
