#!/bin/bash

# Script to build Docker image for Raspberry Pi

echo "Building Docker image for Raspberry Pi..."

# Create buildx builder if it doesn't exist
docker buildx inspect mybuilder >/dev/null 2>&1 || docker buildx create --name mybuilder

# Use the builder
docker buildx use mybuilder

# Build and push to local registry for ARM64
docker buildx build --platform linux/arm64 -t lpr-system-rpi .

echo "Build complete! To run on Raspberry Pi:"
echo "docker run -p 8000:8000 lpr-system-rpi"