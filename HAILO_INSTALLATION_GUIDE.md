# Official Hailo-8L AI HAT+ Installation Guide
## For Raspberry Pi 5 with Ubuntu

Based on official Raspberry Pi and Hailo documentation.

## ⚠️ IMPORTANT: OS Requirement

**The Hailo AI HAT+ officially requires Raspberry Pi OS Bookworm (64-bit).**

You are currently running **Ubuntu 25.04**, which is NOT officially supported by Raspberry Pi's Hailo packages.

### Your Options:

#### Option 1: Switch to Raspberry Pi OS (Recommended for Hailo)
1. Download Raspberry Pi OS Bookworm (64-bit)
2. Flash to SD card using Raspberry Pi Imager
3. Boot and follow installation steps below

#### Option 2: Continue with Ubuntu (Manual Compilation - Already Done!)
✅ You've already compiled HailoRT from source
❌ But hardware is still not detected

---

## Installation Steps (For Raspberry Pi OS)

### 1. Update System
```bash
sudo apt update
sudo apt full-upgrade -y
sudo rpi-update
sudo reboot
```

### 2. Install Hailo Software Packages
```bash
# Install rpicam-apps with Hailo support
sudo apt install rpicam-apps

# Install Hailo post-processing libraries
sudo apt install hailo-all
```

### 3. Verify Installation
```bash
# Check for Hailo device
hailortcli scan

# Expected output: "Hailo-8 device (PCIe)"
```

---

## Current Status on Your Ubuntu System

### ✅ What's Working:
- HailoRT library compiled and installed (v5.1.1)
- Python bindings (`hailo_platform`) installed
- CLI tools (`hailortcli`) available

### ❌ What's Not Working:
- **Hardware not detected** - `hailortcli scan` shows "Hailo devices not found"
- This could be because:
  1. HAT is not physically installed
  2. HAT is not properly seated on GPIO pins
  3. Ubuntu kernel doesn't have Hailo drivers
  4. Power supply is insufficient

---

## Troubleshooting Steps

### 1. Check Physical Connection
```bash
# Power off
sudo shutdown -h now

# Then:
# 1. Disconnect power
# 2. Remove and reseat the Hailo HAT on GPIO pins
# 3. Ensure it's firmly pressed down
# 4. Reconnect power and boot
```

### 2. Check Power Supply
The Hailo-8L requires significant power. Ensure you have:
- **27W USB-C power supply** (official Raspberry Pi power supply)
- Not using a standard 15W phone charger

### 3. Check Kernel Messages
```bash
sudo dmesg | grep -i hailo
sudo dmesg | grep -i pci
```

### 4. Check PCIe Devices
```bash
lspci | grep -i hailo
# or
lspci
```

---

## Alternative: Use Raspberry Pi OS

If you want guaranteed Hailo support, the easiest path is:

1. **Backup your work**:
   ```bash
   cd /home/raai
   tar -czf alpr_backup.tar.gz development/Refine_ALPR
   ```

2. **Flash Raspberry Pi OS Bookworm** to SD card

3. **Restore and install**:
   ```bash
   # After booting Raspberry Pi OS:
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install rpicam-apps hailo-all
   
   # Restore your code
   tar -xzf alpr_backup.tar.gz
   ```

4. **Verify**:
   ```bash
   hailortcli scan
   ```

---

## Next Steps After Hardware Detection

Once `hailortcli scan` shows the Hailo device:

1. Download a VLM model in `.hef` format
2. Test inference speed with `rpicam-hello`
3. Integrate with your ALPR system

---

## Quick Commands Reference

```bash
# Check hardware
hailortcli scan

# Check Python
python3 -c "from hailo_platform import Device; print(Device.scan())"

# Check power
vcgencmd get_throttled
# 0x0 = good, anything else = power issue

# Check PCIe
lspci -v

# Run verification
cd /home/raai/development/Refine_ALPR
python3 verify_hailo.py
```
