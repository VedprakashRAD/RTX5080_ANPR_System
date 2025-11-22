#!/bin/bash
# Quick Hailo Setup - Run this after physically installing the HAT

echo "=============================================="
echo "Hailo-8L Quick Setup"
echo "=============================================="
echo ""

# Step 1: Shutdown
echo "Step 1: Shutting down system for hardware installation..."
echo "After shutdown:"
echo "  1. Disconnect power"
echo "  2. Install Hailo-8L AI HAT+ on GPIO pins"
echo "  3. Reconnect power and boot"
echo ""
read -p "Press ENTER to shutdown now, or Ctrl+C to cancel..."
sudo shutdown -h now
