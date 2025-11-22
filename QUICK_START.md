# Complete ALPR System - Quick Start Guide

## System is Running on Port 8000

**Access Points:**
- Dashboard: http://localhost:8000
- Live Feed: http://localhost:8000/video_feed
- API Docs: http://localhost:8000/docs
- API Endpoint: http://localhost:8000/extract-license-plate

## Start/Stop Commands

**Start System:**
```bash
cd /home/raai/development/Refine_ALPR
python3 app.py
```

**Stop System:**
Press `Ctrl+C` in the terminal

## Complete Workflow Documentation

All documentation files are located in:
```
/home/raai/.gemini/antigravity/brain/5f321322-3cdc-4fff-b388-168c4dd70a4d/
```

### Documentation Files:

1. **complete_flow.md** - 15-stage pipeline diagram and architecture
2. **walkthrough.md** - Implementation guide and usage examples
3. **system_flow.md** - Original system architecture
4. **two_stage_detection_guide.md** - Vehicle→Plate detection details
5. **implementation_plan.md** - Original migration plan
6. **task.md** - Complete task checklist

### Download All Documentation:

**Option 1: Copy to Project Root**
```bash
cd /home/raai/development/Refine_ALPR
mkdir -p docs
cp /home/raai/.gemini/antigravity/brain/5f321322-3cdc-4fff-b388-168c4dd70a4d/*.md docs/
```

**Option 2: Create Archive**
```bash
cd /home/raai/development/Refine_ALPR
tar -czf alpr_documentation.tar.gz \
  /home/raai/.gemini/antigravity/brain/5f321322-3cdc-4fff-b388-168c4dd70a4d/*.md
```

**Option 3: View in Browser**
Open these files directly:
- file:///home/raai/.gemini/antigravity/brain/5f321322-3cdc-4fff-b388-168c4dd70a4d/complete_flow.md
- file:///home/raai/.gemini/antigravity/brain/5f321322-3cdc-4fff-b388-168c4dd70a4d/walkthrough.md

## Quick Configuration

Edit `.env` file to customize:
```bash
nano /home/raai/development/Refine_ALPR/.env
```

Key settings:
- `API_PORT=8000` (already set)
- `RTSP_URL=rtsp://...` (your camera)
- `COMPARE_ENGINES=false` (set to true for benchmarking)
- `USE_LLAMA_CPP=false` (set to true for LlamaCPP)

## System Status Check

```bash
# Check if running
curl http://localhost:8000/docs

# Test with image
curl -X POST -F "image=@test_plate.jpg" \
  http://localhost:8000/extract-license-plate
```

## Complete Project Structure

```
/home/raai/development/Refine_ALPR/
├── app.py                          # Main FastAPI application
├── .env                            # Configuration file
├── services/
│   ├── vehicle_detector.py        # YOLOv8n vehicle detection
│   ├── yolo_plate_detector.py     # License plate detection
│   ├── image_enhancer.py          # OpenCV preprocessing
│   ├── license_plate_service.py   # OCR service (Ollama)
│   └── llamacpp_service.py        # OCR service (LlamaCPP)
├── utils/
│   ├── indian_number_plates_guide.py  # Plate validation
│   └── internet_checker.py        # Connectivity check
├── lpr_system.py                  # Legacy LPR system
├── lpr_headless.py                # Background service
├── system_test.py                 # System tests
└── docs/                          # Documentation (after copy)
    ├── complete_flow.md
    ├── walkthrough.md
    └── ...
```
