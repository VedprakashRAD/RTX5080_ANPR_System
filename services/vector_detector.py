"""
Vector Detector for Directional Vehicle Detection

Determines if a vehicle is approaching or receding from camera
to prevent duplicate processing from entry/exit cameras.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
import time

class VectorDetector:
    """Detects vehicle movement direction (approaching vs receding)"""
    
    def __init__(self, camera_direction: str, trigger_line_y: int = None):
        """
        Initialize vector detector
        
        Args:
            camera_direction: "IN" or "OUT"
            trigger_line_y: Y-coordinate of trigger line (default: middle of frame)
        """
        self.camera_direction = camera_direction
        self.trigger_line_y = trigger_line_y
        
        # Track vehicle movement history
        # {track_id: {'positions': [(bbox, timestamp), ...], 'triggered': bool}}
        self.vehicle_tracks = {}
        
        # Cleanup old tracks every 60 seconds
        self.last_cleanup = time.time()
        self.track_timeout = 10.0  # seconds
    
    def update_track(self, track_id: int, bbox: Tuple[int, int, int, int]) -> None:
        """
        Update vehicle track with new position
        
        Args:
            track_id: Unique vehicle ID from ByteTrack
            bbox: (x1, y1, x2, y2) bounding box
        """
        current_time = time.time()
        
        if track_id not in self.vehicle_tracks:
            self.vehicle_tracks[track_id] = {
                'positions': [],
                'triggered': False,
                'first_seen': current_time
            }
        
        # Add position to history
        self.vehicle_tracks[track_id]['positions'].append({
            'bbox': bbox,
            'timestamp': current_time,
            'area': self._calculate_area(bbox),
            'center_y': (bbox[1] + bbox[3]) / 2
        })
        
        # Keep only last 10 positions
        if len(self.vehicle_tracks[track_id]['positions']) > 10:
            self.vehicle_tracks[track_id]['positions'] = \
                self.vehicle_tracks[track_id]['positions'][-10:]
        
        # Periodic cleanup
        if current_time - self.last_cleanup > 60:
            self._cleanup_old_tracks()
    
    def is_approaching(self, track_id: int) -> Optional[bool]:
        """
        Determine if vehicle is approaching camera
        
        Returns:
            True: Approaching (process this vehicle)
            False: Receding (ignore this vehicle)
            None: Not enough data yet
        """
        if track_id not in self.vehicle_tracks:
            return None
        
        history = self.vehicle_tracks[track_id]['positions']
        
        # Need at least 3 frames to determine direction
        if len(history) < 3:
            return None
        
        # Method 1: Size-based detection (primary)
        # Approaching vehicle = getting larger
        is_growing = self._is_size_increasing(history)
        
        # Method 2: Movement direction (secondary)
        # For IN camera: vehicle moving down (y increasing)
        # For OUT camera: vehicle moving up (y decreasing)
        is_correct_direction = self._is_correct_direction(history)
        
        # Both methods must agree
        approaching = is_growing and is_correct_direction
        
        return approaching
    
    def has_crossed_trigger_line(self, track_id: int) -> bool:
        """
        Check if vehicle has crossed the trigger line
        This is when we capture the "golden frame"
        
        Returns:
            True if crossed and not yet triggered
        """
        if track_id not in self.vehicle_tracks:
            return False
        
        # Already triggered this vehicle
        if self.vehicle_tracks[track_id]['triggered']:
            return False
        
        history = self.vehicle_tracks[track_id]['positions']
        if len(history) < 2:
            return False
        
        # Get trigger line (default: middle of frame)
        trigger_y = self.trigger_line_y if self.trigger_line_y else 540  # Assume 1080p
        
        # Check if vehicle crossed the line
        prev_center_y = history[-2]['center_y']
        curr_center_y = history[-1]['center_y']
        
        # For IN camera: crossing from top to bottom
        # For OUT camera: crossing from bottom to top
        if self.camera_direction == "IN":
            crossed = prev_center_y < trigger_y <= curr_center_y
        else:  # OUT
            crossed = prev_center_y > trigger_y >= curr_center_y
        
        if crossed:
            self.vehicle_tracks[track_id]['triggered'] = True
            print(f"🎯 Track {track_id} crossed trigger line [{self.camera_direction}]")
        
        return crossed
    
    def get_best_frame_bbox(self, track_id: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the best bounding box for this track
        (largest/closest to camera)
        
        Returns:
            (x1, y1, x2, y2) or None
        """
        if track_id not in self.vehicle_tracks:
            return None
        
        history = self.vehicle_tracks[track_id]['positions']
        if not history:
            return None
        
        # Find frame with largest area (closest to camera)
        best_frame = max(history, key=lambda x: x['area'])
        return best_frame['bbox']
    
    def _is_size_increasing(self, history: List[Dict]) -> bool:
        """Check if vehicle size is increasing (approaching)"""
        if len(history) < 3:
            return False
        
        # Compare last 3 frames
        recent = history[-3:]
        areas = [frame['area'] for frame in recent]
        
        # Calculate trend
        # Approaching: area should increase by at least 5% over 3 frames
        growth_rate = (areas[-1] - areas[0]) / areas[0]
        
        return growth_rate > 0.05  # 5% growth = approaching
    
    def _is_correct_direction(self, history: List[Dict]) -> bool:
        """Check if vehicle is moving in correct direction for this camera"""
        if len(history) < 3:
            return False
        
        # Get Y-coordinate movement
        recent = history[-3:]
        y_positions = [frame['center_y'] for frame in recent]
        
        # Calculate movement direction
        y_movement = y_positions[-1] - y_positions[0]
        
        # IN camera: vehicle should move down (y increasing)
        # OUT camera: vehicle should move up (y decreasing)
        if self.camera_direction == "IN":
            return y_movement > 10  # Moving down
        else:  # OUT
            return y_movement < -10  # Moving up
    
    def _calculate_area(self, bbox: Tuple[int, int, int, int]) -> float:
        """Calculate bounding box area"""
        x1, y1, x2, y2 = bbox
        return (x2 - x1) * (y2 - y1)
    
    def _cleanup_old_tracks(self) -> None:
        """Remove tracks that haven't been updated recently"""
        current_time = time.time()
        
        tracks_to_remove = []
        for track_id, data in self.vehicle_tracks.items():
            if current_time - data['first_seen'] > self.track_timeout:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.vehicle_tracks[track_id]
        
        if tracks_to_remove:
            print(f"🧹 Cleaned up {len(tracks_to_remove)} old tracks")
        
        self.last_cleanup = current_time
    
    def reset_track(self, track_id: int) -> None:
        """Reset a track (after processing)"""
        if track_id in self.vehicle_tracks:
            del self.vehicle_tracks[track_id]
    
    def get_active_tracks_count(self) -> int:
        """Get number of currently tracked vehicles"""
        return len(self.vehicle_tracks)
