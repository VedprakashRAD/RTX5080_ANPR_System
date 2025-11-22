# Hybrid OCR Setup: Doctr + SmolVLM2 🚀

## Overview
We have implemented a **Hybrid OCR Strategy** to achieve the best balance of speed and accuracy.

### How it Works
1.  **Stage 1: Doctr (Speed)** 🏎️
    -   **Technology**: Specialized OCR SDK (PyTorch backend).
    -   **Speed**: < 1 second.
    -   **Role**: Fast pass. Tries to read the plate instantly.
    -   **Validation**: Checks confidence score (> 0.7) and regex pattern.

2.  **Stage 2: SmolVLM2 (Accuracy)** 🧠
    -   **Technology**: Vision-Language Model (2.2B parameters).
    -   **Speed**: ~24 seconds.
    -   **Role**: Fallback. Used only if Doctr fails or is unsure.
    -   **Benefit**: Understands context and handles difficult/non-standard plates.

## Configuration
Enabled in `.env`:
```bash
OCR_STRATEGY=HYBRID
```

## Performance Test Results
-   **Test Image**: `test_plate.jpg` (Non-standard "TES123")
-   **Doctr Result**: `TES23` (Rejected - Invalid format)
-   **Fallback**: Triggered SmolVLM2
-   **Final Result**: `The Indian license plate number is "TES123"` ✅
-   **Conclusion**: The safety net works! Doctr was fast but inaccurate for this specific image; SmolVLM2 saved the day.

## Next Steps for Optimization
To get more "Fast Pass" successes:
1.  **Tune Doctr**: Adjust image preprocessing (contrast, resizing) to help Doctr read better.
2.  **Relax Validation**: If you expect non-standard plates (like "TES123"), update the regex in `services/hybrid_ocr_service.py`.

## Usage
The system now automatically uses this strategy.
-   **API**: `http://localhost:8000/extract-license-plate`
-   **Logs**: Check logs to see "Hybrid OCR: Doctr success" or "Falling back to SmolVLM2".
