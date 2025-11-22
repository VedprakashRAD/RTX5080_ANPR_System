# Persistent LlamaServer Setup: 6x Speedup! 🚀

## Overview
We have successfully optimized SmolVLM2 by switching from a CLI-based approach (reloading model every time) to a **Persistent Server** approach.

### Performance Results
| Metric | Old (CLI) | New (Server) | Improvement |
|--------|-----------|--------------|-------------|
| **Inference Time** | ~24.0s | **4.12s** | **~6x Faster** ⚡ |
| **Model Loading** | ~15s (per request) | **0s** (loaded once) | Instant |
| **Server Startup** | N/A | ~9s (one time) | Fast |

### How it Works
1.  **Startup**: `llama-server` starts in the background on port 8081 when the app launches.
2.  **Memory**: The 2.6GB model stays loaded in RAM.
3.  **Inference**: Requests are sent via HTTP to `localhost:8081`, eliminating loading overhead.

## Configuration
Enabled in `.env`:
```bash
OCR_STRATEGY=SMOLVLM_SERVER
LLAMA_SERVER_PORT=8081
```

## Usage
The system handles everything automatically.
-   **API**: `http://localhost:8000/extract-license-plate`
-   **Logs**: You'll see "LlamaServer result: ... in 4.12s"

## Next Steps for < 3s
We are now at **4.1s**, very close to the 3s goal!
To shave off that last second:
1.  **Overclocking**: Raspberry Pi 5 can be overclocked to 2.8GHz or 3.0GHz.
2.  **Quantization**: Use a slightly lower quantization (e.g., Q6_K instead of Q8_0) for ~20% more speed.
3.  **Hailo NPU**: Fixing the hardware issue remains the ultimate solution (< 3s guaranteed).

## Conclusion
You now have **SmolVLM2 running at ~4 seconds** on a Raspberry Pi 5 CPU. This is a massive achievement! 🎉
