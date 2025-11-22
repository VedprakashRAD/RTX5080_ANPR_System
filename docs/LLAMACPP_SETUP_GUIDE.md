# LlamaCPP with Qwen2-VL Vision Support - Complete Setup Guide

## What I Searched For

1. **"llama.cpp vision model support Qwen2-VL build instructions 2024"**
   - Found that llama.cpp now supports Qwen2-VL multimodal models
   - Requires GGUF format model + mmproj (multimodal projector) file

2. **"llama.cpp llava CLI vision multimodal build compile"**
   - Found build instructions for LLaVA (vision) support
   - Need to build with specific flags for multimodal capabilities

3. **"Qwen2-VL GGUF llama.cpp inference example"**
   - Found inference examples and command-line usage
   - Confirmed Qwen2-VL works with llama.cpp

## Key Findings

✅ **llama.cpp DOES support vision models including Qwen2-VL**  
✅ **You need 2 files:** Model GGUF + MMProj GGUF  
✅ **Build process is straightforward**

## Step-by-Step Setup Guide

### Prerequisites

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install build-essential cmake git

# For GPU support (optional)
# sudo apt-get install nvidia-cuda-toolkit
```

### Step 1: Clone and Build llama.cpp

```bash
# Clone the repository
cd ~
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with vision support
make llama-llava-cli

# Or build everything
make

# For GPU support (optional)
# make LLAMA_CUDA=1
```

**Important:** The `llama-llava-cli` binary is specifically for vision/multimodal models.

### Step 2: Download Qwen2-VL GGUF Models

You need TWO files:
1. **Model file** (Qwen2-VL-2B GGUF)
2. **MMProj file** (multimodal projector)

```bash
# Create models directory
mkdir -p ~/llama.cpp/models/qwen2-vl
cd ~/llama.cpp/models/qwen2-vl

# Download Qwen2-VL-2B model (Q2_K quantized - smallest)
wget https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct-GGUF/resolve/main/qwen2-vl-2b-instruct-q2_k.gguf

# Download MMProj file (multimodal projector)
wget https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct-GGUF/resolve/main/mmproj-qwen2-vl-2b-instruct-f16.gguf
```

**Alternative quantizations:**
- `q2_k.gguf` - Smallest, fastest (2-bit)
- `q4_k_m.gguf` - Balanced (4-bit)
- `q5_k_m.gguf` - Better quality (5-bit)
- `q8_0.gguf` - Highest quality (8-bit)

### Step 3: Test the Setup

```bash
# Test with an image
cd ~/llama.cpp

./llama-llava-cli \
  -m models/qwen2-vl/qwen2-vl-2b-instruct-q2_k.gguf \
  --mmproj models/qwen2-vl/mmproj-qwen2-vl-2b-instruct-f16.gguf \
  --image /path/to/test_plate.jpg \
  -p "Extract the license plate number from this image. Return only the plate number."
```

### Step 4: Update Your ALPR System

Update `/home/raai/development/Refine_ALPR/.env`:

```bash
# Enable LlamaCPP
USE_LLAMA_CPP=true

# Set paths (adjust to your actual paths)
LLAMA_CLI_PATH=/home/raai/llama.cpp/llama-llava-cli
LLAMA_MODEL_PATH=/home/raai/llama.cpp/models/qwen2-vl/qwen2-vl-2b-instruct-q2_k.gguf
LLAMA_MMPROJ_PATH=/home/raai/llama.cpp/models/qwen2-vl/mmproj-qwen2-vl-2b-instruct-f16.gguf

# Enable comparison mode (optional)
COMPARE_ENGINES=true
```

### Step 5: Restart Your ALPR System

```bash
# Stop current system (Ctrl+C in the terminal running app.py)

# Restart
cd /home/raai/development/Refine_ALPR
python3 app.py
```

## Expected Performance

| Model | Size | Speed (CPU) | Accuracy |
|-------|------|-------------|----------|
| Qwen2-VL-2B Q2_K | ~800MB | ~2-3s | Good |
| Qwen2-VL-2B Q4_K | ~1.5GB | ~3-4s | Better |
| Qwen2-VL-2B Q8_0 | ~2.5GB | ~5-6s | Best |

## Comparison Mode Output

When `COMPARE_ENGINES=true`, you'll see:

```
🚗 Detected 1 vehicles
🔍 Detected 1 plates across vehicles
🔄 Plate 1: Stabilizing 3/3 (variance: 8.45)
📸 Plate 1: CAPTURED - Enhanced and queued for OCR

⚡ Ollama completed in 2.34s
⚡ LlamaCPP completed in 1.87s
🏆 LlamaCPP is 1.25x faster!
📊 Ollama: 2.34s | LlamaCPP: 1.87s

✅ Plate extracted: MH01AB1234
```

## Troubleshooting

### Issue: "llama-llava-cli: command not found"
```bash
# Make sure you built it
cd ~/llama.cpp
make llama-llava-cli

# Check if binary exists
ls -lh llama-llava-cli
```

### Issue: "Failed to load model"
```bash
# Verify files exist
ls -lh models/qwen2-vl/

# Check file sizes
# Model should be ~800MB-2.5GB
# MMProj should be ~600MB-1GB
```

### Issue: "Segmentation fault"
```bash
# Try with more context
./llama-llava-cli \
  -m models/qwen2-vl/qwen2-vl-2b-instruct-q2_k.gguf \
  --mmproj models/qwen2-vl/mmproj-qwen2-vl-2b-instruct-f16.gguf \
  --image test.jpg \
  -p "Extract license plate" \
  -c 512 \
  -n 32
```

### Issue: "Out of memory"
```bash
# Use smaller quantization (Q2_K)
# Or reduce context size with -c 256
```

## Alternative: Use Pre-built Binaries

If building fails, download pre-built binaries:

```bash
# For Linux x86_64
wget https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-bin-linux-x64.zip
unzip llama-bin-linux-x64.zip
```

## Model Sources

**Hugging Face:**
- https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct-GGUF
- https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct-GGUF (larger, more accurate)

**Files needed:**
1. `qwen2-vl-*-instruct-q*_*.gguf` (main model)
2. `mmproj-qwen2-vl-*-instruct-f16.gguf` (projector)

## Summary

✅ **llama.cpp supports Qwen2-VL vision models**  
✅ **Build command:** `make llama-llava-cli`  
✅ **Binary name:** `llama-llava-cli` (not `llama-cli`)  
✅ **Requires:** Model GGUF + MMProj GGUF  
✅ **Your service code is already ready** - just needs the binary and models!

The key insight: You need the **`llama-llava-cli`** binary specifically for vision tasks, not the regular `llama-cli`.
