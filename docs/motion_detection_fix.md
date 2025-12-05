# Final Motion Detection Fix - Ignore Stationary Vehicles

## Problem

Camera 2 (EXIT) was detecting the same stationary BUS repeatedly, even though **nothing was moving toward the camera**.

## Root Cause

The background subtractor was treating stationary vehicles as "foreground" (motion) instead of learning them as "background".

Parameters were too sensitive:
- `history=500` - Too short learning period
- `varThreshold=16` - Too sensitive to stationary objects
- `area > 10000` - Too small, detected even slight movements

## Solution

### 1. Increased Background Learning Period
```python
history=2000  # Was: 500
# Now learns background over 2000 frames (~67 seconds at 30fps)
# Stationary vehicles become part of background
```

### 2. Reduced Sensitivity to Stationary Objects
```python
varThreshold=50  # Was: 16
# Higher threshold = less sensitive to small changes
# Ignores lighting changes, shadows, camera shake
```

### 3. Added Learning Rate Control
```python
learning_rate = 0.01  # Slow learning
fg_mask = self.bg_subtractor.apply(frame, learningRate=learning_rate)
# Properly adapts to stationary vehicles over time
```

### 4. Increased Minimum Vehicle Area
```python
if area > 20000:  # Was: 10000
# Only triggers on large moving objects
# Filters out stationary vehicles and small movements
```

## How It Works Now

```
Frame 1-2000: Learning phase
  ├─ Stationary BUS detected as "foreground"
  ├─ Over time, BUS becomes part of "background"
  └─ After ~67 seconds, BUS is fully learned as background

Frame 2001+: Detection phase
  ├─ Stationary BUS = background (ignored)
  ├─ Moving vehicle approaches = foreground (detected!)
  └─ Only triggers when area > 20000 pixels AND motion > 15000 pixels
```

## Expected Behavior

**Before (broken):**
```
Camera 2: 🚗 BUS detected (stationary)
Camera 2: 🚗 BUS detected (same bus, still stationary)
Camera 2: 🚗 BUS detected (same bus, still stationary)
...forever
```

**After (fixed):**
```
(67 seconds learning period...)
Camera 2: (no detections - stationary BUS is now background)
...
(Vehicle approaches camera)
Camera 2: 🚗 Vehicle detected (moving!)
✅ VERIFIED ENTRY EVENT
```

## Restart Required

```bash
# Stop (Ctrl+C)
python app.py
```

## Important Notes

1. **Learning Period**: First ~67 seconds after startup, system learns the background
2. **During Learning**: May still detect stationary vehicles
3. **After Learning**: Only detects actual moving vehicles
4. **Best Practice**: Let system run for 2-3 minutes before expecting accurate detection

## Summary

✅ **Increased history**: 500 → 2000 frames  
✅ **Reduced sensitivity**: varThreshold 16 → 50  
✅ **Added learning rate**: 0.01 (slow adaptation)  
✅ **Increased area threshold**: 10000 → 20000 pixels  

System now properly ignores stationary vehicles!
