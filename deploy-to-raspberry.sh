#!/bin/bash

# Script to deploy the Docker container to Raspberry Pi

echo "Deploying LPR System to Raspberry Pi..."

# Check if Docker is installed
if ! command -v docker &> /dev/null
then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Build the image
echo "Building Docker image..."
docker build -t lpr-system-rpi .

# Run the container
echo "Starting LPR System container..."
docker run -d \
  --name lpr-system \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/vehicle_images:/app/vehicle_images \
  -v $(pwd)/temp_roi:/app/temp_roi \
  -v $(pwd)/lpr_logs.db:/app/lpr_logs.db \
  lpr-system-rpi

echo "LPR System is now running on port 8000"
echo "Access the web interface at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"