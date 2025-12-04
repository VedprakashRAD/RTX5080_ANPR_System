# RTX5080 ANPR System

**High-Performance License Plate Recognition System**  
Optimized for NVIDIA RTX 5080 GPU deployment with multi-camera support

---

## 🚀 Features

### Core Capabilities
- **Multi-Camera Support**: 4 RTSP cameras (2 gates × 2 cameras: IN/OUT)
- **High-Accuracy Detection**: YOLOv8 plate detection with 75% confidence threshold
- **Vision LLM OCR**: SmolVLM/Qwen-VL for license plate text extraction
- **Duplicate Suppression**: 30-second cooldown to prevent spam
- **MongoDB Integration**: Persistent storage with camera tracking and direction
- **Real-Time Processing**: GPU-accelerated for high-performance deployment

### Production Features
- ✅ No duplicate detections (30s cooldown)
- ✅ High confidence threshold (0.75 = 75%)
- ✅ MongoDB persistence with GridFS support
- ✅ Camera source tracking (RAHQ-G1-IN-01, etc.)
- ✅ Direction tracking (IN/OUT)
- ✅ SQLite fallback logging
- ✅ Automatic temp file cleanup

---

## 📋 System Requirements

### Hardware
- **GPU**: NVIDIA RTX 5080 (16GB VRAM) or equivalent
- **RAM**: 16GB minimum
- **Storage**: 50GB+ for models and logs
- **Network**: Gigabit Ethernet for RTSP streams

### Software
- **OS**: Ubuntu 20.04+ / Linux
- **Python**: 3.11+
- **CUDA**: 12.0+
- **Docker**: Optional (recommended)

---

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone git@github.com:deepak-kumar-swain/RTX5080_ANPR_System.git
cd RTX5080_ANPR_System
```

### 2. Install Dependencies
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Important:** Update camera credentials in `.env`:
```bash
# Example for Camera 1
CAMERA_G1_IN_01_URL=rtsp://admin:YourActualPassword@192.168.30.101:554/Streaming/Channels/101
```

### 4. Install Ollama (for Vision LLM)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull vision model
ollama pull qwen2.5vl:3b
# or
ollama pull smolvlm2:2.2b

# Start Ollama server
ollama serve
```

---

## 🎯 Quick Start

### Start the System
```bash
# Activate virtual environment
source venv/bin/activate

# Start ANPR system
python app.py
```

### Access Services
- **API Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Camera Feed**: http://localhost:8000/video_feed

---

## 📡 API Endpoints

### 1. Extract License Plate (POST)
**Endpoint:** `/extract-license-plate`

**Request:**
```bash
curl -X POST "http://localhost:8000/extract-license-plate" \
  -F "image=@car.jpg"
```

**Response:**
```json
{
  "success": true,
  "internet": true,
  "registrationNo": "MH12AB1234",
  "yolo_detections": [
    {
      "bbox": [100, 200, 300, 400],
      "confidence": 0.95
    }
  ],
  "yolo_confidence": 0.95
}
```

---

## 🎥 Camera Configuration

### 4-Camera Layout

**Gate 1:**
- `RAHQ-G1-IN-01` (192.168.30.101) - Entry
- `RAHQ-G1-OUT-02` (192.168.30.102) - Exit

**Gate 2:**
- `RAHQ-G2-IN-03` (192.168.30.103) - Entry
- `RAHQ-G2-OUT-04` (192.168.30.104) - Exit

### Camera Selection
```bash
# Edit .env to select active camera
ACTIVE_CAMERA=CAMERA_G1_IN_01
```

### Test Camera Configuration
```bash
python utils/camera_config.py
```

---

## 🗄️ Database Configuration

### MongoDB (Primary Storage)
```bash
# .env configuration
MONGODB_ENABLED=true
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=anpr_system
```

**Data Stored:**
- License plate number
- Camera ID (RAHQ-G1-IN-01, etc.)
- Direction (IN/OUT)
- Timestamp
- Confidence score
- Image path (GridFS)

### SQLite (Fallback)
```bash
DB_FILE=lpr_logs.db
```

---

## ⚙️ Configuration

### Key Settings (.env)

**Camera Settings:**
```bash
ACTIVE_CAMERA=CAMERA_G1_IN_01
CAMERA_RESOLUTION=1080p
CAMERA_FPS=25
```

**Detection Settings:**
```bash
# Confidence thresholds (production-grade)
VEHICLE_CONFIDENCE=0.6
PLATE_CONFIDENCE=0.75

# Duplicate suppression
DUPLICATE_COOLDOWN=30  # seconds
```

**Ollama Settings:**
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5vl:3b
```

**API Settings:**
```bash
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 🔧 Production Deployment

### Systemd Service
```bash
# Create service file
sudo nano /etc/systemd/system/anpr.service
```

```ini
[Unit]
Description=ANPR System
After=network.target

[Service]
Type=simple
User=anpr
WorkingDirectory=/home/anpr/RTX5080_ANPR_System
Environment="PATH=/home/anpr/RTX5080_ANPR_System/venv/bin"
ExecStart=/home/anpr/RTX5080_ANPR_System/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable anpr
sudo systemctl start anpr
sudo systemctl status anpr
```

---

## 📊 Performance Metrics

### GPU Utilization (RTX 5080)
- **Inference Time**: 150-300ms per image
- **VRAM Usage**: ~3-4GB (with qwen2.5vl:3b)
- **Throughput**: 3-6 FPS per camera
- **Accuracy**: >90% (with 0.75 confidence threshold)

### Detection Accuracy
- **Confidence Threshold**: 0.75 (75%)
- **False Positive Rate**: <10%
- **Duplicate Suppression**: 30s cooldown
- **OCR Success Rate**: ~80-95% (depends on image quality)

---

## 🐛 Troubleshooting

### Common Issues

**1. Camera Connection Failed**
```bash
# Test RTSP stream
ffplay rtsp://admin:password@192.168.30.101:554/Streaming/Channels/101

# Check camera connectivity
ping 192.168.30.101
```

**2. Ollama Not Running**
```bash
# Start Ollama server
ollama serve

# Check if model is installed
ollama list
```

**3. MongoDB Connection Failed**
```bash
# Start MongoDB
sudo systemctl start mongod

# Check status
sudo systemctl status mongod
```

**4. Low Detection Accuracy**
- Increase camera resolution
- Adjust lighting conditions
- Clean camera lens
- Check RTSP stream quality

---

## 📁 Project Structure

```
RTX5080_ANPR_System/
├── app.py                      # Main application
├── lpr_system.py              # LPR processing logic
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── services/
│   ├── yolo_plate_detector.py    # YOLOv8 plate detection
│   ├── vehicle_detector.py       # Vehicle detection
│   ├── llama_server_service.py   # Vision LLM OCR
│   ├── mongodb_sync.py           # MongoDB integration
│   ├── image_enhancer.py         # Image preprocessing
│   └── temp_cleanup.py           # Temp file management
├── utils/
│   ├── camera_config.py          # Camera management
│   └── indian_number_plates_guide.py  # Plate validation
├── models/                    # YOLO models
└── docs/
    └── CAMERA_CONFIGURATION.md   # Camera setup guide
```

---

## 🔐 Security

### Best Practices
1. **Never commit `.env` file** (contains passwords)
2. **Use strong camera passwords**
3. **Restrict API access** (add authentication)
4. **Enable MongoDB authentication**
5. **Use HTTPS in production**
6. **Regular security updates**

---

## 📝 License

This project is proprietary software for ReadyAssist R&D Campus.

---

## 🤝 Support

For issues or questions:
- **GitHub Issues**: https://github.com/deepak-kumar-swain/RTX5080_ANPR_System/issues
- **Email**: support@readyassist.com

---

## 🎉 Changelog

### v2.0.0 (Production Release)
- ✅ Removed 21,571 duplicate database entries
- ✅ Raised confidence threshold from 0.3 to 0.75
- ✅ Added 30-second duplicate suppression
- ✅ Enabled MongoDB integration with camera tracking
- ✅ Removed all Raspberry Pi code and dependencies
- ✅ Optimized for high-performance GPU deployment
- ✅ Cleaned up test files and documentation

### v1.0.0 (Initial Release)
- Basic ANPR functionality
- Single camera support
- SQLite logging

---

**Built with ❤️ for high-performance license plate recognition**