#!/usr/bin/env python3
"""
Hailo‑8L CLIP encoder wrapper.

Provides:
    get_image_embedding(image_path) -> np.ndarray
"""

import os
from pathlib import Path
import numpy as np
from PIL import Image
import hailort
import hailort.sdk as hailo_sdk
from dotenv import load_dotenv

# -------------------------------------------------
# Load configuration from .env (fallback defaults)
# -------------------------------------------------
load_dotenv()   # reads .env from the project root

HAILO_MODEL_PATH = os.getenv(
    "HAILO_VISION_ENGINE",
    "/home/raai/models/hailo/clip_vision.hailo"
)

# -------------------------------------------------
# Initialise the Hailo inference engine (singleton)
# -------------------------------------------------
def _load_engine():
    if not Path(HAILO_MODEL_PATH).exists():
        raise FileNotFoundError(f"Hailo model not found: {HAILO_MODEL_PATH}")

    device = hailo_sdk.Device()                     # first available NPU
    network = device.get_network(HAILO_MODEL_PATH)  # load compiled network
    engine = network.create_engine()                # inference engine (batch=1)
    return engine

_ENGINE = _load_engine()   # global, reused for every call

# -------------------------------------------------
# Image preprocessing – CLIP expects 224×224, normalized
# -------------------------------------------------
def _preprocess(image_path: str) -> np.ndarray:
    img = Image.open(image_path).convert("RGB")
    img = img.resize((224, 224), Image.BILINEAR)

    # CLIP normalization (same as torchvision.transforms.Normalize)
    img_np = np.array(img).astype(np.float32) / 255.0
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    std  = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
    img_np = (img_np - mean) / std

    # Hailo expects NHWC (batch, height, width, channels)
    img_np = np.expand_dims(img_np, axis=0)   # shape (1,224,224,3)
    return img_np

# -------------------------------------------------
# Public API
# -------------------------------------------------
def get_image_embedding(image_path: str) -> np.ndarray:
    """
    Run the CLIP vision encoder on the Hailo‑8L and return a 1‑D float32 embedding.
    Typical size for CLIP‑ViT‑B/32 is 512.
    """
    input_tensor = _preprocess(image_path)          # NHWC float32
    result = _ENGINE.run({"input": input_tensor})   # dict of output tensors
    embedding = result["output"]                     # shape (1, 512)
    embedding = np.squeeze(embedding)                # -> (512,)
    return embedding

# -------------------------------------------------
# Simple CLI test (optional)
# -------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python hailo_clip.py <image_path>")
        sys.exit(1)

    emb = get_image_embedding(sys.argv[1])
    print(f"Embedding shape: {emb.shape}")
    print(f"First 5 values: {emb[:5]}")
