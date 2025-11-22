# Complete ALPR System - Documentation Index

## 📊 System Status
- **Running:** ✅ Yes (Port 8000)
- **Access:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 📚 Documentation Files

### 1. [QUICK_START.md](../QUICK_START.md)
**Start here!** Quick commands to run and access the system.

### 2. [complete_flow.md](complete_flow.md) ⭐
**Visual flow diagram** showing all 15 stages with Mermaid chart and performance metrics.

### 3. [walkthrough.md](walkthrough.md)
Complete implementation guide with configuration examples and usage instructions.

### 4. [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)
What's completed, what's pending, and backup information.

### 5. [system_flow.md](system_flow.md)
High-level architecture overview with component descriptions.

### 6. [two_stage_detection_guide.md](two_stage_detection_guide.md)
Technical details of the Vehicle→Plate detection pipeline.

## 🎯 Quick Links

**Visual Flow Diagram:**
![ALPR Pipeline](/home/raai/development/Refine_ALPR/docs/alpr_flow_diagram.png)

**Configuration File:**
- [.env](../.env) - All system settings

**Backup Location:**
- `/home/raai/development/Refine_ALPR/backup_original/`

## 🚀 Common Tasks

### Start System
```bash
cd /home/raai/development/Refine_ALPR
python3 app.py
```

### View Live Feed
Open: http://localhost:8000

### Test API
```bash
curl -X POST -F "image=@test.jpg" http://localhost:8000/extract-license-plate
```

### Edit Configuration
```bash
nano /home/raai/development/Refine_ALPR/.env
```

## 📋 What's Not Yet Developed

1. **MongoDB Sync** - Code ready, needs configuration
2. **LlamaCPP Binary** - Service ready, needs installation
3. **Temp File Cleanup** - Not implemented
4. **Metrics Dashboard** - Not implemented
5. **Configuration UI** - Not implemented

See [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) for details.

## 🔧 System Architecture

**15-Stage Pipeline:**
1-3: Input & Trigger (RTSP, Motion)
4-6: Detection (Vehicle, Plate, Stability)
7-9: Preprocessing (Crop, Sharp, Enhance)
10-12: OCR (Ollama/LlamaCPP/Compare)
13-15: Validation & Storage (Format, Type, DB)

**Key Components:**
- `app.py` - Main FastAPI server
- `services/vehicle_detector.py` - YOLOv8n vehicle detection
- `services/yolo_plate_detector.py` - Plate detection
- `services/image_enhancer.py` - OpenCV preprocessing
- `services/license_plate_service.py` - OCR (Ollama)
- `services/llamacpp_service.py` - OCR (LlamaCPP)
