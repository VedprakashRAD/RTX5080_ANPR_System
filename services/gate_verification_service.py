"""
Gate Verification Service
Manages dual-camera verification for gate entry/exit events
"""

import time
import uuid
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()


class PendingDetection:
    """Represents a detection from one camera awaiting verification"""
    
    def __init__(self, detection_id: str, gate_name: str, camera_id: str, 
                 camera_position: str, detection_data: Dict):
        self.detection_id = detection_id
        self.gate_name = gate_name
        self.camera_id = camera_id
        self.camera_position = camera_position  # 'ENTRY' or 'EXIT'
        self.detection_time = time.time()
        
        # Vehicle data
        self.vehicle_type = detection_data.get('type', 'UNKNOWN')
        self.color = detection_data.get('color', 'UNKNOWN')
        self.plate = detection_data.get('plate')
        self.confidence = detection_data.get('confidence', 0.0)
        self.image_path = detection_data.get('image_path')
        
        # Verification status
        self.verified = False
        self.matched_detection_id = None
        
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'detection_id': self.detection_id,
            'gate_name': self.gate_name,
            'camera_id': self.camera_id,
            'camera_position': self.camera_position,
            'vehicle_type': self.vehicle_type,
            'color': self.color,
            'plate': self.plate,
            'confidence': self.confidence,
            'detection_time': datetime.fromtimestamp(self.detection_time).isoformat(),
            'image_path': self.image_path,
            'verified': self.verified,
            'matched_detection_id': self.matched_detection_id
        }


class GateVerificationService:
    """Manages dual-camera verification for gate events"""
    
    def __init__(self, config: Dict = None):
        self.pending_detections = {}  # {detection_id: PendingDetection}
        
        # Default configuration
        self.config = config or {}
        self.verification_window = self.config.get('verification_window_seconds', 5)
        self.min_match_score = self.config.get('min_match_score', 60)
        self.max_pending_time = 30  # Clean up after 30 seconds
        
        # Gate pairs configuration
        self.gate_pairs = self.config.get('gate_pairs', {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            },
            'GATE2': {
                'entry_camera_id': 'GATE2-ENTRY',
                'exit_camera_id': 'GATE2-EXIT'
            }
        })
        
        # Database connection
        self.db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': os.getenv('MYSQL_USER', 'debian-sys-maint'),
            'password': os.getenv('MYSQL_PASSWORD', 'hEAefJ9yDcmcJtR3'),
            'database': os.getenv('MYSQL_DATABASE', 'anpr_system')
        }
        
        # Initialize database tables
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Gate detections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gate_detections (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    detection_id VARCHAR(50) UNIQUE NOT NULL,
                    gate_name VARCHAR(20) NOT NULL,
                    camera_id VARCHAR(50) NOT NULL,
                    camera_position ENUM('ENTRY', 'EXIT') NOT NULL,
                    vehicle_type VARCHAR(50),
                    color VARCHAR(50),
                    plate VARCHAR(20),
                    confidence_score FLOAT,
                    detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    image_path VARCHAR(255),
                    verified BOOLEAN DEFAULT FALSE,
                    matched_detection_id VARCHAR(50),
                    INDEX idx_gate_time (gate_name, detection_time),
                    INDEX idx_verified (verified, detection_time)
                )
            """)
            
            # Verified gate events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verified_gate_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_id VARCHAR(50) UNIQUE NOT NULL,
                    gate_name VARCHAR(20) NOT NULL,
                    event_type ENUM('ENTRY', 'EXIT') NOT NULL,
                    vehicle_type VARCHAR(50),
                    color VARCHAR(50),
                    plate VARCHAR(20),
                    entry_camera_detection_id VARCHAR(50),
                    exit_camera_detection_id VARCHAR(50),
                    entry_image_path VARCHAR(255),
                    exit_image_path VARCHAR(255),
                    verification_score FLOAT,
                    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    dwell_time_seconds INT,
                    INDEX idx_plate (plate),
                    INDEX idx_event_time (event_time)
                )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Gate verification database tables initialized")
            
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
    
    def register_camera_detection(self, camera_id: str, detection_data: Dict) -> Optional[Dict]:
        """
        Register a detection from one camera and attempt verification
        
        Args:
            camera_id: Camera identifier (e.g., "GATE1-ENTRY")
            detection_data: Detection data from API
        
        Returns:
            Dict with verification status or None
        """
        # Clean up expired detections
        self._cleanup_expired_detections()
        
        # Determine gate and camera position
        gate_info = self._get_gate_info(camera_id)
        if not gate_info:
            print(f"⚠️ Camera {camera_id} not configured for dual-camera verification")
            return None
        
        gate_name, camera_position = gate_info
        
        # Create detection record
        detection_id = self._generate_detection_id()
        detection = PendingDetection(
            detection_id, gate_name, camera_id, camera_position, detection_data
        )
        
        # Save to pending detections
        self.pending_detections[detection_id] = detection
        
        # Save to database
        self._save_detection_to_db(detection)
        
        print(f"\n📸 CAMERA DETECTION: {camera_id}")
        print(f"   Gate: {gate_name}, Position: {camera_position}")
        print(f"   Type: {detection.vehicle_type}, Color: {detection.color}")
        print(f"   Plate: {detection.plate or 'Not visible'}")
        print(f"   Detection ID: {detection_id}")
        
        # Try to find matching detection from paired camera
        match = self._find_matching_detection(detection)
        
        if match:
            # Verification successful!
            verified_event = self._create_verified_event(detection, match)
            
            # Mark both detections as verified
            detection.verified = True
            detection.matched_detection_id = match.detection_id
            match.verified = True
            match.matched_detection_id = detection_id
            
            # Update database
            self._update_detection_verified(detection)
            self._update_detection_verified(match)
            
            # Remove from pending
            self.pending_detections.pop(detection_id, None)
            self.pending_detections.pop(match.detection_id, None)
            
            return {
                'verified': True,
                'event_id': verified_event['event_id'],
                'match_score': verified_event['verification_score'],
                'event_type': verified_event['event_type'],
                'plate': verified_event['plate'],
                'vehicle_type': verified_event['vehicle_type']
            }
        else:
            print(f"   ⏳ Waiting for paired camera detection...")
            print(f"   Pending detections: {len(self.pending_detections)}")
            return {
                'verified': False,
                'detection_id': detection_id,
                'status': 'PENDING',
                'waiting_for': self._get_paired_camera(camera_id)
            }
    
    def _get_gate_info(self, camera_id: str) -> Optional[Tuple[str, str]]:
        """Get gate name and camera position for a camera"""
        camera_id_upper = camera_id.upper()
        
        for gate_name, gate_config in self.gate_pairs.items():
            entry_cam = gate_config['entry_camera_id'].upper()
            exit_cam = gate_config['exit_camera_id'].upper()
            
            if camera_id_upper == entry_cam:
                return (gate_name, 'ENTRY')
            elif camera_id_upper == exit_cam:
                return (gate_name, 'EXIT')
        
        return None
    
    def _get_paired_camera(self, camera_id: str) -> Optional[str]:
        """Get the paired camera ID"""
        camera_id_upper = camera_id.upper()
        
        for gate_config in self.gate_pairs.values():
            entry_cam = gate_config['entry_camera_id'].upper()
            exit_cam = gate_config['exit_camera_id'].upper()
            
            if camera_id_upper == entry_cam:
                return gate_config['exit_camera_id']
            elif camera_id_upper == exit_cam:
                return gate_config['entry_camera_id']
        
        return None
    
    def _find_matching_detection(self, detection: PendingDetection) -> Optional[PendingDetection]:
        """Find matching detection from paired camera"""
        current_time = time.time()
        candidates = []
        
        print(f"   🔍 Searching for matching detection from paired camera...")
        
        for det_id, pending_det in list(self.pending_detections.items()):
            # Skip self
            if det_id == detection.detection_id:
                continue
            
            # Must be from same gate
            if pending_det.gate_name != detection.gate_name:
                continue
            
            # Must be from opposite camera position
            if pending_det.camera_position == detection.camera_position:
                continue
            
            # Must not be already verified
            if pending_det.verified:
                continue
            
            # Calculate match score
            score = self._calculate_match_score(detection, pending_det, current_time)
            
            time_diff = abs(current_time - pending_det.detection_time)
            print(f"      Candidate: {det_id[:8]}... (score: {score:.1f}, time diff: {time_diff:.1f}s)")
            
            if score >= self.min_match_score:
                candidates.append((pending_det, score))
        
        if candidates:
            # Return best match
            best_match = max(candidates, key=lambda x: x[1])
            print(f"   ✅ MATCH FOUND! Score: {best_match[1]:.1f}")
            return best_match[0]
        
        return None
    
    def _calculate_match_score(self, det1: PendingDetection, det2: PendingDetection, 
                               current_time: float) -> float:
        """
        Calculate matching score between two detections
        
        Scoring:
        - Vehicle Type Match: 40 points (required)
        - Color Match: 30 points (exact) or 15 points (similar)
        - Timing Window: 20 points (within verification_window) or 10 points (acceptable)
        - Plate Match: 10 points (if both have plates and they match)
        """
        score = 0.0
        
        # Vehicle type match (REQUIRED)
        if det1.vehicle_type == det2.vehicle_type:
            score += 40
        else:
            return 0  # No match if types don't match
        
        # Color match
        if det1.color == det2.color:
            score += 30
        elif self._colors_similar(det1.color, det2.color):
            score += 15
        
        # Timing window
        time_diff = abs(det1.detection_time - det2.detection_time)
        if time_diff <= self.verification_window:
            score += 20
        elif time_diff <= self.verification_window * 2:
            score += 10
        else:
            return 0  # Outside acceptable time window
        
        # Plate match (bonus if both have plates)
        if det1.plate and det2.plate:
            if det1.plate == det2.plate:
                score += 10
            else:
                # Plates don't match - reduce score
                score -= 20
        
        return score
    
    def _colors_similar(self, color1: str, color2: str) -> bool:
        """Check if two colors are similar"""
        if not color1 or not color2:
            return False
        
        similar_colors = {
            'WHITE': ['SILVER', 'GREY', 'LIGHT GREY'],
            'BLACK': ['DARK GREY', 'GREY', 'DARK'],
            'BLUE': ['DARK BLUE', 'NAVY', 'LIGHT BLUE'],
            'RED': ['MAROON', 'DARK RED', 'BURGUNDY'],
            'SILVER': ['WHITE', 'GREY', 'LIGHT GREY'],
            'GREY': ['WHITE', 'SILVER', 'BLACK', 'DARK GREY']
        }
        
        color1_upper = color1.upper()
        color2_upper = color2.upper()
        
        if color1_upper in similar_colors:
            return color2_upper in similar_colors[color1_upper]
        
        return False
    
    def _create_verified_event(self, det1: PendingDetection, det2: PendingDetection) -> Dict:
        """Create verified event from two matching detections"""
        # Determine which is entry and which is exit
        entry_det = det1 if det1.camera_position == 'ENTRY' else det2
        exit_det = det2 if det2.camera_position == 'EXIT' else det1
        
        # Determine final plate (prefer one with plate visible)
        final_plate = None
        if entry_det.plate and exit_det.plate:
            if entry_det.plate == exit_det.plate:
                final_plate = entry_det.plate
                print(f"   ✅ Plates match: {final_plate}")
            else:
                final_plate = entry_det.plate  # Prefer entry plate
                print(f"   ⚠️ Plate mismatch - Entry: {entry_det.plate}, Exit: {exit_det.plate}")
                print(f"   ℹ️ Using entry plate: {final_plate}")
        elif entry_det.plate:
            final_plate = entry_det.plate
            print(f"   ℹ️ Using entry plate: {final_plate}")
        elif exit_det.plate:
            final_plate = exit_det.plate
            print(f"   ℹ️ Using exit plate: {final_plate}")
        else:
            print(f"   ⚠️ No plate detected on either camera")
        
        # Calculate verification score
        verification_score = self._calculate_match_score(det1, det2, time.time())
        
        # Determine event type based on timing
        event_type = 'ENTRY' if entry_det.detection_time < exit_det.detection_time else 'EXIT'
        
        # Calculate dwell time
        dwell_time = int(abs(exit_det.detection_time - entry_det.detection_time))
        
        event_id = self._generate_event_id()
        
        event = {
            'event_id': event_id,
            'gate_name': det1.gate_name,
            'event_type': event_type,
            'vehicle_type': det1.vehicle_type,
            'color': det1.color,
            'plate': final_plate,
            'entry_camera_detection_id': entry_det.detection_id,
            'exit_camera_detection_id': exit_det.detection_id,
            'entry_image_path': entry_det.image_path,
            'exit_image_path': exit_det.image_path,
            'verification_score': verification_score,
            'dwell_time_seconds': dwell_time
        }
        
        # Save to database
        self._save_verified_event(event)
        
        print(f"\n✅ VERIFIED {event_type} EVENT: {event_id}")
        print(f"   Gate: {det1.gate_name}")
        print(f"   Entry Camera: {entry_det.camera_id} → Exit Camera: {exit_det.camera_id}")
        print(f"   Vehicle: {det1.vehicle_type}, {det1.color}")
        print(f"   Plate: {final_plate or 'Not detected'}")
        print(f"   Verification Score: {verification_score:.1f}/100")
        print(f"   Dwell Time: {dwell_time}s")
        
        return event
    
    def _save_detection_to_db(self, detection: PendingDetection):
        """Save detection to database"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
                INSERT INTO gate_detections 
                (detection_id, gate_name, camera_id, camera_position, vehicle_type, 
                 color, plate, confidence_score, detection_time, image_path, verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                detection.detection_id,
                detection.gate_name,
                detection.camera_id,
                detection.camera_position,
                detection.vehicle_type,
                detection.color,
                detection.plate,
                detection.confidence,
                datetime.fromtimestamp(detection.detection_time),
                detection.image_path,
                detection.verified
            )
            
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Database save error: {e}")
    
    def _update_detection_verified(self, detection: PendingDetection):
        """Update detection as verified in database"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
                UPDATE gate_detections 
                SET verified = TRUE, matched_detection_id = %s
                WHERE detection_id = %s
            """
            
            cursor.execute(query, (detection.matched_detection_id, detection.detection_id))
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Database update error: {e}")
    
    def _save_verified_event(self, event: Dict):
        """Save verified event to database"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
                INSERT INTO verified_gate_events 
                (event_id, gate_name, event_type, vehicle_type, color, plate,
                 entry_camera_detection_id, exit_camera_detection_id, 
                 entry_image_path, exit_image_path, verification_score, dwell_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                event['event_id'],
                event['gate_name'],
                event['event_type'],
                event['vehicle_type'],
                event['color'],
                event['plate'],
                event['entry_camera_detection_id'],
                event['exit_camera_detection_id'],
                event['entry_image_path'],
                event['exit_image_path'],
                event['verification_score'],
                event['dwell_time_seconds']
            )
            
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"   💾 Verified event saved to database")
            
        except Exception as e:
            print(f"   ❌ Database save error: {e}")
    
    def _cleanup_expired_detections(self):
        """Remove expired pending detections"""
        current_time = time.time()
        expired = []
        
        for detection_id, detection in list(self.pending_detections.items()):
            if current_time - detection.detection_time > self.max_pending_time:
                expired.append(detection_id)
        
        for detection_id in expired:
            detection = self.pending_detections[detection_id]
            print(f"\n⏰ DETECTION EXPIRED: {detection_id}")
            print(f"   Camera: {detection.camera_id}")
            print(f"   No matching detection from paired camera")
            print(f"   Timeout: {self.max_pending_time}s")
            
            # Keep in database but remove from pending
            del self.pending_detections[detection_id]
    
    def _generate_detection_id(self) -> str:
        """Generate unique detection ID"""
        return f"DET-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"EVT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    def get_pending_detections(self) -> List[Dict]:
        """Get all pending detections"""
        return [det.to_dict() for det in self.pending_detections.values()]
