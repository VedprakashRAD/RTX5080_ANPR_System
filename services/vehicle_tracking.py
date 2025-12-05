"""
Vehicle Tracking Service
Tracks vehicles across multiple cameras and matches entry/exit detections
"""

import time
import uuid
from typing import Dict, Optional, List
from datetime import datetime
import mysql.connector
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Import gate verification service
try:
    from services.gate_verification_service import GateVerificationService
    GATE_VERIFICATION_AVAILABLE = True
except ImportError:
    GATE_VERIFICATION_AVAILABLE = False
    print("⚠️ Gate verification service not available")


class VehicleSession:
    """Represents an active vehicle session"""
    
    def __init__(self, vehicle_id: str, camera_id: str, detection_data: Dict):
        self.vehicle_id = vehicle_id
        self.entry_camera = camera_id
        self.entry_time = time.time()
        self.vehicle_type = detection_data.get('type', 'UNKNOWN')
        self.color = detection_data.get('color', 'UNKNOWN')
        self.plate = detection_data.get('plate')
        self.confidence = detection_data.get('confidence', 0.0)
        self.entry_image = detection_data.get('image_path')
        self.exit_camera = None
        self.exit_time = None
        self.exit_image = None
        self.dwell_time = None
        # Track if plate was visible on entry
        self.entry_plate_visible = bool(self.plate)
        
    def to_dict(self):
        """Convert session to dictionary"""
        return {
            'vehicle_id': self.vehicle_id,
            'plate': self.plate,
            'vehicle_type': self.vehicle_type,
            'color': self.color,
            'entry_camera': self.entry_camera,
            'exit_camera': self.exit_camera,
            'entry_time': datetime.fromtimestamp(self.entry_time).isoformat(),
            'exit_time': datetime.fromtimestamp(self.exit_time).isoformat() if self.exit_time else None,
            'dwell_time': self.dwell_time,
            'confidence': self.confidence,
            'entry_plate_visible': self.entry_plate_visible
        }


class VehicleTrackingService:
    """Track vehicles across multiple cameras"""
    
    def __init__(self, config_path: str = 'config/cameras.json'):
        self.active_sessions = {}  # {vehicle_id: VehicleSession}
        self.session_timeout = 180  # 3 minutes
        self.min_dwell_time = 5  # Minimum 5 seconds between entry/exit
        self.max_dwell_time = 300  # Maximum 5 minutes between entry/exit
        self.match_threshold = 60  # Minimum score for matching
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize gate verification service if configured
        self.gate_verification = None
        if GATE_VERIFICATION_AVAILABLE and 'gate_pairs' in self.config:
            gate_config = {
                'gate_pairs': self._resolve_gate_pairs(self.config.get('gate_pairs', {})),
                'verification_window_seconds': 5,
                'min_match_score': 60
            }
            self.gate_verification = GateVerificationService(gate_config)
            print("✅ Gate verification service initialized")
        
        # Database connection
        self.db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': os.getenv('MYSQL_USER', 'debian-sys-maint'),
            'password': os.getenv('MYSQL_PASSWORD', 'hEAefJ9yDcmcJtR3'),
            'database': os.getenv('MYSQL_DATABASE', 'anpr_system')
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load camera configuration"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"⚠️ Could not load config: {e}")
            return {}
    
    def _resolve_gate_pairs(self, gate_pairs: Dict) -> Dict:
        """Resolve environment variables in gate pairs config"""
        resolved = {}
        for gate_name, gate_config in gate_pairs.items():
            resolved[gate_name] = {
                'entry_camera_id': os.path.expandvars(gate_config.get('entry_camera_id', '')),
                'exit_camera_id': os.path.expandvars(gate_config.get('exit_camera_id', '')),
                'verification_window_seconds': gate_config.get('verification_window_seconds', 5),
                'min_match_score': gate_config.get('min_match_score', 60),
                'require_verification': gate_config.get('require_verification', True)
            }
        return resolved
    
    def register_detection(self, camera_id: str, detection_data: Dict) -> Optional[VehicleSession]:
        """
        Register a new vehicle detection
        
        Args:
            camera_id: Camera identifier (e.g., "GATE1-ENTRY", "GATE1-EXIT")
            detection_data: Detection data from API
        
        Returns:
            VehicleSession object or verification result
        """
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        # Check if this camera is part of a gate pair requiring verification
        if self.gate_verification and self._is_gate_camera(camera_id):
            print(f"\n🔐 Using dual-camera verification for {camera_id}")
            verification_result = self.gate_verification.register_camera_detection(
                camera_id, detection_data
            )
            
            if verification_result and verification_result.get('verified'):
                # Create a session object for compatibility
                session = VehicleSession(
                    verification_result.get('event_id', 'VERIFIED'),
                    camera_id,
                    detection_data
                )
                session.verification_status = 'VERIFIED'
                session.verification_score = verification_result.get('match_score', 0)
                return session
            else:
                # Return pending status
                return None
        
        # Fallback to original single-camera logic
        # Determine camera type based on ID
        if self._is_entry_camera(camera_id):
            return self._handle_entry(camera_id, detection_data)
        elif self._is_exit_camera(camera_id):
            return self._handle_exit(camera_id, detection_data)
        else:
            return self._handle_standalone(camera_id, detection_data)
    
    def _is_gate_camera(self, camera_id: str) -> bool:
        """Check if camera is part of a configured gate pair"""
        if not self.gate_verification:
            return False
        
        camera_id_upper = camera_id.upper()
        for gate_config in self.gate_verification.gate_pairs.values():
            if (camera_id_upper == gate_config['entry_camera_id'].upper() or 
                camera_id_upper == gate_config['exit_camera_id'].upper()):
                return True
        return False
    
    def _is_entry_camera(self, camera_id: str) -> bool:
        """Check if camera is an entry camera"""
        camera_id_upper = str(camera_id).upper()
        return ('ENTRY' in camera_id_upper or 
                'IN' in camera_id_upper or 
                camera_id_upper in ['1', '3'])
    
    def _is_exit_camera(self, camera_id: str) -> bool:
        """Check if camera is an exit camera"""
        camera_id_upper = str(camera_id).upper()
        return ('EXIT' in camera_id_upper or 
                'OUT' in camera_id_upper or 
                camera_id_upper in ['2', '4'])
    
    def _handle_entry(self, camera_id: str, detection_data: Dict) -> VehicleSession:
        """Handle entry camera detection"""
        vehicle_id = self._generate_vehicle_id()
        session = VehicleSession(vehicle_id, camera_id, detection_data)
        self.active_sessions[vehicle_id] = session
        
        print(f"\n🚗 NEW VEHICLE ENTRY: {vehicle_id}")
        print(f"   Camera: {camera_id}")
        print(f"   Type: {session.vehicle_type}, Color: {session.color}")
        print(f"   Plate: {session.plate or 'Not visible'}")
        if session.plate:
            print(f"   ℹ️ Plate visible on entry")
        else:
            print(f"   ⚠️ Plate NOT visible on entry")
        print(f"   Active sessions: {len(self.active_sessions)}")
        
        return session
    
    def _handle_exit(self, camera_id: str, detection_data: Dict) -> Optional[VehicleSession]:
        """Handle exit camera detection - match with entry"""
        print(f"\n🚪 EXIT DETECTION on {camera_id}")
        print(f"   Type: {detection_data.get('type')}, Color: {detection_data.get('color')}")
        print(f"   Plate: {detection_data.get('plate') or 'Not visible'}")
        
        # Find matching entry session
        match = self._find_matching_session(detection_data)
        
        if match:
            # Update session with exit data
            match.exit_camera = camera_id
            match.exit_time = time.time()
            match.dwell_time = int(match.exit_time - match.entry_time)
            match.exit_image = detection_data.get('image_path')
            
            # Handle plate visibility combination
            exit_plate = detection_data.get('plate')
            
            if match.entry_plate_visible and not exit_plate:
                # Entry had plate, exit doesn't - keep entry plate
                print(f"   ℹ️ Keeping entry plate: {match.plate}")
            elif not match.entry_plate_visible and exit_plate:
                # Entry didn't have plate, exit does - use exit plate
                match.plate = exit_plate
                print(f"   ℹ️ Using exit plate: {match.plate}")
            elif match.entry_plate_visible and exit_plate:
                # Both have plates - verify they match
                if match.plate == exit_plate:
                    print(f"   ✅ Plates match: {match.plate}")
                else:
                    print(f"   ⚠️ Plate mismatch - Entry: {match.plate}, Exit: {exit_plate}")
                    # Prefer entry plate as it was the first detection
                    print(f"   ℹ️ Keeping entry plate: {match.plate}")
            else:
                # Neither had plate
                print(f"   ⚠️ No plate detected on entry or exit")
            
            print(f"✅ VEHICLE MATCHED: {match.vehicle_id}")
            print(f"   Entry: {match.entry_camera} → Exit: {match.exit_camera}")
            print(f"   Dwell time: {match.dwell_time}s")
            print(f"   Final plate: {match.plate or 'Not detected'}")
            
            # Save complete record to database
            self._save_vehicle_record(match)
            
            # Remove from active sessions
            del self.active_sessions[match.vehicle_id]
            
            return match
        else:
            # No match found - treat as standalone detection
            print(f"⚠️ NO MATCHING ENTRY FOUND")
            print(f"   Possible reasons:")
            print(f"   - Vehicle entered before system started")
            print(f"   - Entry detection missed")
            print(f"   - Vehicle from different gate")
            return self._handle_standalone(camera_id, detection_data)
    
    def _handle_standalone(self, camera_id: str, detection_data: Dict) -> VehicleSession:
        """Handle standalone detection (no entry/exit pairing)"""
        vehicle_id = self._generate_vehicle_id()
        session = VehicleSession(vehicle_id, camera_id, detection_data)
        
        print(f"\n📸 STANDALONE DETECTION: {vehicle_id}")
        print(f"   Camera: {camera_id}")
        print(f"   Type: {session.vehicle_type}, Color: {session.color}")
        print(f"   Plate: {session.plate or 'Not visible'}")
        
        # Save immediately (no pairing)
        self._save_vehicle_record(session)
        
        return session
    
    def _find_matching_session(self, detection_data: Dict) -> Optional[VehicleSession]:
        """Find matching vehicle session based on characteristics"""
        current_time = time.time()
        candidates = []
        
        print(f"   🔍 Searching {len(self.active_sessions)} active sessions...")
        
        for vehicle_id, session in list(self.active_sessions.items()):
            # Calculate match score
            score = self._calculate_match_score(session, detection_data, current_time)
            
            if score > 0:
                time_diff = current_time - session.entry_time
                print(f"      Candidate: {vehicle_id} (score: {score:.1f}, time: {time_diff:.1f}s)")
                
            if score >= self.match_threshold:
                candidates.append((session, score))
        
        if candidates:
            # Return best match
            best_match = max(candidates, key=lambda x: x[1])
            print(f"   ✓ Best match: {best_match[0].vehicle_id} (score: {best_match[1]:.1f})")
            return best_match[0]
        
        return None
    
    def _calculate_match_score(self, session: VehicleSession, detection_data: Dict, current_time: float) -> float:
        """
        Calculate matching score between session and new detection
        
        Scoring:
        - Type match: 40 points (required)
        - Color match: 30 points (exact) or 15 points (similar)
        - Time window: 20 points (optimal) or 10 points (acceptable)
        - Confidence: up to 10 points
        """
        score = 0.0
        
        # Type match (required - must match exactly)
        detection_type = detection_data.get('type', 'UNKNOWN')
        if session.vehicle_type == detection_type:
            score += 40
        else:
            return 0  # No match if type doesn't match
        
        # Color match
        detection_color = detection_data.get('color', 'UNKNOWN')
        if session.color == detection_color:
            score += 30
        elif self._colors_similar(session.color, detection_color):
            score += 15
        
        # Time window (5-300 seconds is acceptable)
        time_diff = current_time - session.entry_time
        if self.min_dwell_time <= time_diff <= self.max_dwell_time:
            score += 20
        elif 2 <= time_diff <= 600:
            score += 10
        else:
            return 0  # Outside acceptable time window
        
        # Confidence boost
        avg_confidence = (session.confidence + detection_data.get('confidence', 0)) / 2
        score += avg_confidence * 0.1
        
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
    
    def _save_vehicle_record(self, session: VehicleSession):
        """Save vehicle record to MySQL database"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert into vehicle_sessions table
            query = """
                INSERT INTO vehicle_sessions 
                (vehicle_id, plate, vehicle_type, color, entry_camera, exit_camera, 
                 entry_time, exit_time, dwell_time_seconds, entry_image_path, 
                 exit_image_path, confidence_score, entry_plate_visible)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                session.vehicle_id,
                session.plate,
                session.vehicle_type,
                session.color,
                session.entry_camera,
                session.exit_camera,
                datetime.fromtimestamp(session.entry_time),
                datetime.fromtimestamp(session.exit_time) if session.exit_time else None,
                session.dwell_time,
                session.entry_image,
                session.exit_image,
                session.confidence,
                session.entry_plate_visible
            )
            
            cursor.execute(query, values)
            conn.commit()
            
            print(f"   💾 Saved to database: {session.vehicle_id}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Database error: {e}")
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired = []
        
        for vehicle_id, session in self.active_sessions.items():
            if current_time - session.entry_time > self.session_timeout:
                expired.append(vehicle_id)
        
        for vehicle_id in expired:
            session = self.active_sessions[vehicle_id]
            print(f"\n⏰ SESSION EXPIRED: {vehicle_id}")
            print(f"   Entry time: {datetime.fromtimestamp(session.entry_time).strftime('%H:%M:%S')}")
            print(f"   Timeout: {self.session_timeout}s")
            
            # Save as entry-only record
            self._save_vehicle_record(session)
            del self.active_sessions[vehicle_id]
    
    def _generate_vehicle_id(self) -> str:
        """Generate unique vehicle ID"""
        return f"VEH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions"""
        return [session.to_dict() for session in self.active_sessions.values()]