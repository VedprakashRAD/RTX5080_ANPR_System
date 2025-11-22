# Hailo-8L AI HAT+ Setup Guide

## Current Status
✅ **Software Installed**: HailoRT library (v5.1.1) and Python bindings are ready
❌ **Hardware Not Detected**: Hailo-8L AI HAT+ needs to be physically installed

## Physical Installation Steps

### 1. Power Down the Raspberry Pi 5
```bash
sudo shutdown -h now
```
Wait for the system to completely power off (green LED stops blinking).

### 2. Install the Hailo-8L AI HAT+
1. **Disconnect power** from the Raspberry Pi 5
2. **Align the HAT** with the 40-pin GPIO header on the Raspberry Pi 5
3. **Firmly press down** the HAT onto the GPIO pins until fully seated
4. **Secure with standoffs** (if provided) to prevent movement

### 3. Power On and Verify

After physical installation, power on the Raspberry Pi and run:

```bash
# Check if Hailo device is detected
hailortcli scan

# Expected output: "Hailo-8 device (PCIe)" or similar
# If you see "Hailo devices not found", check the connection
```

### 4. Verify Python Bindings

```bash
python3 -c "from hailo_platform import Device; print('Hailo SDK ready!')"
```

## Next Steps After Hardware Detection

Once `hailortcli scan` shows the Hailo device:

1. **Download a pre-compiled VLM model** in `.hef` format
2. **Update vision_service.py** to use Hailo acceleration
3. **Test inference speed** (target: < 3 seconds)

## Troubleshooting

### "Hailo devices not found"
- Check HAT is firmly seated on GPIO pins
- Verify power supply is adequate (5V/5A recommended for Pi 5 + HAT)
- Try reseating the HAT
- Check `dmesg | grep -i hailo` for kernel messages

### Python import hangs
- This is normal if hardware isn't detected
- Will work once hardware is properly installed

## Verification Script

Run this after installation:
```bash
cd /home/raai/development/Refine_ALPR
python3 verify_hailo.py
```
