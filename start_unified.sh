#!/bin/bash
# Unified ANPR System Startup Script
# Starts API + Multi-Camera Processor + Gate Verification

cd /home/raai/development/ANPR/RTX5080_ALPR

echo "======================================================================"
echo "🚀 Starting Complete ANPR System with Gate Verification"
echo "======================================================================"
echo ""
echo "This will start:"
echo "  ✅ FastAPI Server (port 8000)"
echo "  ✅ Multi-Camera Processor"
echo "  ✅ Dual-Camera Gate Verification"
echo "  ✅ Vehicle Tracking Service"
echo ""
echo "Access:"
echo "  📡 API: http://localhost:8000"
echo "  📚 Docs: http://localhost:8000/docs"
echo "  📹 Video: http://localhost:8000/video_feed"
echo ""
echo "======================================================================"
echo ""

# Suppress OpenCV warnings
export OPENCV_LOG_LEVEL=ERROR
export OPENCV_VIDEOIO_DEBUG=0

# Start the unified system
python3 app.py
