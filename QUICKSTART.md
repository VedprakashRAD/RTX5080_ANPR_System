# Quick Start Guide - RTX5080 ANPR System

## 🚀 **Run the Project in 5 Minutes**

### **Step 1: Install System Dependencies**

```bash
# Update system
sudo apt-get update

# Install OpenCV dependencies
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libopencv-dev \
    python3-opencv \
    libgl1-mesa-glx \
    libglib2.0-0

# Install MySQL
sudo apt-get install -y mysql-server
```

### **Step 2: Install Python Dependencies**

```bash
cd /home/raai/development/ANPR/RTX5080_ALPR

# Install all requirements
pip3 install -r requirements.txt

# Verify OpenCV installation
python3 -c "import cv2; print(f'✅ OpenCV {cv2.__version__} installed')"
```

### **Step 3: Install Ollama and Model**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download vision model (3B - optimized)
ollama pull qwen2.5vl:3b

# Keep model loaded in memory
ollama run qwen2.5vl:3b
# Press Ctrl+D to exit, model stays loaded
```

### **Step 4: Setup MySQL Database**

```bash
cd /home/raai/development/ANPR/RTX5080_ALPR

# Run setup script
chmod +x setup_mysql.sh
./setup_mysql.sh

# Verify database
sudo mysql --defaults-file=/etc/mysql/debian.cnf -e "SHOW DATABASES LIKE 'anpr_system';"
```

### **Step 5: Configure Cameras (Optional)**

Edit `config/cameras.json` with your camera details:

```json
{
  "cameras": [
    {
      "id": "GATE1-ENTRY",
      "rtsp_url": "rtsp://admin:password@192.168.1.101:554/stream",
      "enabled": true
    }
  ]
}
```

### **Step 6: Start the API**

```bash
cd /home/raai/development/ANPR/RTX5080_ALPR

# Start API server
python3 app.py
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### **Step 7: Test the API**

**Open browser:**
```
http://localhost:8000/docs
```

**Or test with curl:**
```bash
curl -X POST "http://localhost:8000/api/extract-license-plate" \
  -F "image=@test_image.jpg" \
  -F "camera_id=TEST"
```

---

## ✅ **Verify Everything is Working**

### **Check Services:**

```bash
# 1. Check API
curl http://localhost:8000/docs

# 2. Check Ollama
ollama ps

# 3. Check MySQL
sudo systemctl status mysql

# 4. Check GPU
nvidia-smi
```

### **Expected Results:**

```
✅ API: Running on port 8000
✅ Ollama: qwen2.5vl:3b loaded (5.8GB VRAM)
✅ MySQL: Active and running
✅ GPU: 100% usage when processing
```

---

## 🎯 **Quick Test**

### **Test with Sample Image:**

```bash
cd /home/raai/development/ANPR/RTX5080_ALPR

# Download test image
wget https://example.com/car_with_plate.jpg -O test_car.jpg

# Test API
curl -X POST "http://localhost:8000/api/extract-license-plate" \
  -F "image=@test_car.jpg" \
  -F "camera_id=TEST-CAMERA"
```

### **Expected Response:**

```json
{
  "success": true,
  "plate": "MH16RH7022",
  "vehicle": {
    "type": "CAR",
    "color": "White"
  },
  "confidence": 0.95,
  "camera_id": "TEST-CAMERA",
  "processing_time_ms": 333
}
```

---

## 🔧 **Troubleshooting**

### **Issue: OpenCV Import Error**

```bash
# Error: ImportError: libGL.so.1: cannot open shared object file
sudo apt-get install -y libgl1-mesa-glx

# Error: ImportError: libgthread-2.0.so.0
sudo apt-get install -y libglib2.0-0
```

### **Issue: Ollama Not Found**

```bash
# Check if Ollama is installed
which ollama

# If not found, install:
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
sudo systemctl start ollama
```

### **Issue: MySQL Connection Error**

```bash
# Start MySQL
sudo systemctl start mysql

# Check status
sudo systemctl status mysql

# Run setup again
./setup_mysql.sh
```

### **Issue: Slow Response (> 1 second)**

```bash
# Check if multiple models loaded
ollama ps

# Should show ONLY qwen2.5vl:3b
# If you see qwen2.5vl:7b, remove it:
ollama rm qwen2.5vl:7b

# Restart Ollama
sudo systemctl restart ollama
ollama run qwen2.5vl:3b
```

---

## 📊 **Monitor Performance**

### **Real-time Monitoring:**

```bash
# Terminal 1: Watch API logs
cd /home/raai/development/ANPR/RTX5080_ALPR
python3 app.py

# Terminal 2: Watch GPU usage
watch -n 1 nvidia-smi

# Terminal 3: Watch database
watch -n 2 'sudo mysql --defaults-file=/etc/mysql/debian.cnf -e "SELECT COUNT(*) FROM anpr_system.vehicle_logs;"'
```

---

## 🎉 **You're Ready!**

Your ANPR system is now running with:
- ✅ 333ms response time
- ✅ 95%+ accuracy
- ✅ Multi-camera support
- ✅ MySQL database
- ✅ Web monitoring

**Next Steps:**
1. Configure your cameras in `config/cameras.json`
2. Run multi-camera processor: `python3 multi_camera_processor.py`
3. Access database UI: http://localhost:8888
4. View API docs: http://localhost:8000/docs

---

**Need help?** Check the full README.md for detailed documentation.
