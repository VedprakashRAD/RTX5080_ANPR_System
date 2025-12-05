#!/bin/bash
# Start Multi-Camera 24/7 Monitoring System

cd /home/raai/development/ANPR/RTX5080_ALPR

echo "🎥 Multi-Camera 24/7 Monitoring System"
echo "========================================"
echo ""
echo "Starting with cameras from config/cameras.json"
echo ""

python3 multi_camera_processor.py
