"""
MongoDB Session Manager for ANPR Entry/Exit Tracking

Handles:
- Entry session creation
- Exit session completion
- Duration calculation
- Metadata verification
- Security alerts
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import os
from bson import ObjectId
import gridfs
import time
import hashlib

class SessionManager:
    """Manages vehicle entry/exit sessions in MongoDB"""
    
    def __init__(self):
        """Initialize MongoDB connection and GridFS"""
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "anpr_system")
        
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[db_name]
        
        # Collections
        self.sessions = self.db.sessions
        self.alerts = self.db.alerts
        self.manual_review = self.db.manual_review
        self.pending_events = self.db.pending_events  # For event matching
        
        # GridFS for image storage
        self.fs = gridfs.GridFS(self.db)
        
        # Event matching configuration
        self.match_window_seconds = 8  # Time window for front/rear matching
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create MongoDB indexes for performance"""
        try:
            # Sessions indexes
            self.sessions.create_index([("plate", ASCENDING), ("status", ASCENDING)])
            self.sessions.create_index([("entry.timestamp", DESCENDING)])
            self.sessions.create_index([("session_id", ASCENDING)], unique=True)
            
            # Alerts indexes
            self.alerts.create_index([("resolved", ASCENDING), ("severity", ASCENDING)])
            self.alerts.create_index([("timestamp", DESCENDING)])
            
            # Manual review indexes
            self.manual_review.create_index([("reviewed", ASCENDING)])
            self.manual_review.create_index([("timestamp", DESCENDING)])
            
            # Pending events indexes (for event matching)
            self.pending_events.create_index([("timestamp", ASCENDING)], expireAfterSeconds=30)
            self.pending_events.create_index([("camera_id", ASCENDING)])
            
            print("✅ MongoDB indexes created")
        except Exception as e:
            print(f"⚠️ Index creation warning: {e}")
    
    def generate_temp_id(self, vehicle_data: Dict, timestamp: datetime) -> str:
        """
        Generate temporary ID for vehicles without plates
        Format: MAKE_MODEL_COLOR_TIMESTAMP
        """
        make = vehicle_data.get('make', 'UNKNOWN').upper().replace(' ', '_')
        model = vehicle_data.get('model', 'UNKNOWN').upper().replace(' ', '_')
        color = vehicle_data.get('color', 'UNKNOWN').upper().replace(' ', '_')
        time_str = timestamp.strftime('%H%M%S')
        
        return f"{make}_{model}_{color}_{time_str}"
    
    def add_detection_event(self, camera_id: str, plate: Optional[str],
                           vehicle_data: Dict, image_path: str,
                           confidence: float) -> Optional[Dict]:
        """
        Add detection event and try to match with opposite camera
        Returns: Merged event if match found, None if waiting for pair
        """
        try:
            current_time = datetime.now()
            
            # Create event document
            event = {
                'camera_id': camera_id,
                'plate': plate,
                'vehicle': vehicle_data,
                'image_path': image_path,
                'confidence': confidence,
                'timestamp': current_time,
                'processed': False
            }
            
            # Try to find matching event from opposite camera
            match = self._find_matching_event(event)
            
            if match:
                # Found pair! Merge and remove from pending
                merged = self._merge_events(event, match)
                self.pending_events.delete_one({'_id': match['_id']})
                print(f"✅ Matched front/rear pair: {merged.get('plate', 'NO_PLATE')}")
                return merged
            else:
                # No match yet, store as pending
                self.pending_events.insert_one(event)
                print(f"⏳ Event pending match: {camera_id} - {plate or 'NO_PLATE'}")
                return None
                
        except Exception as e:
            print(f"❌ Event matching error: {e}")
            return None
    
    def _find_matching_event(self, event: Dict) -> Optional[Dict]:
        """
        Find matching event from opposite camera within time window
        """
        try:
            # Calculate time window
            min_time = event['timestamp'] - timedelta(seconds=self.match_window_seconds)
            max_time = event['timestamp'] + timedelta(seconds=self.match_window_seconds)
            
            # Find pending events in time window from different camera
            candidates = self.pending_events.find({
                'camera_id': {'$ne': event['camera_id']},
                'timestamp': {'$gte': min_time, '$lte': max_time},
                'processed': False
            })
            
            # Find best metadata match
            best_match = None
            best_score = 0
            
            for candidate in candidates:
                score = self._calculate_metadata_match_score(
                    event['vehicle'],
                    candidate['vehicle']
                )
                
                if score > best_score and score >= 3:  # Require 3/4 match
                    best_score = score
                    best_match = candidate
            
            return best_match
            
        except Exception as e:
            print(f"❌ Match finding error: {e}")
            return None
    
    def _calculate_metadata_match_score(self, vehicle1: Dict, vehicle2: Dict) -> int:
        """
        Calculate metadata match score (0-4)
        Require 3/4 for confident match
        """
        score = 0
        
        # Compare each field
        if vehicle1.get('make', '').lower() == vehicle2.get('make', '').lower():
            score += 1
        if vehicle1.get('model', '').lower() == vehicle2.get('model', '').lower():
            score += 1
        if vehicle1.get('color', '').lower() == vehicle2.get('color', '').lower():
            score += 1
        if vehicle1.get('type', '').lower() == vehicle2.get('type', '').lower():
            score += 1
        
        return score
    
    def _merge_events(self, event1: Dict, event2: Dict) -> Dict:
        """
        Merge front + rear camera events into single record
        Select plate from whichever camera has it
        """
        # Determine which event has the plate
        if event1.get('plate'):
            plate_event = event1
            rear_event = event2
        elif event2.get('plate'):
            plate_event = event2
            rear_event = event1
        else:
            # Neither has plate - use first event as primary
            plate_event = event1
            rear_event = event2
        
        # Use earliest timestamp
        timestamp = min(event1['timestamp'], event2['timestamp'])
        
        # Merge metadata (prefer plate_event)
        merged = {
            'plate': plate_event.get('plate'),
            'vehicle': plate_event['vehicle'],
            'camera_front': plate_event['camera_id'] if plate_event.get('plate') else rear_event['camera_id'],
            'camera_rear': rear_event['camera_id'] if plate_event.get('plate') else plate_event['camera_id'],
            'image_front': plate_event['image_path'] if plate_event.get('plate') else rear_event['image_path'],
            'image_rear': rear_event['image_path'] if plate_event.get('plate') else plate_event['image_path'],
            'timestamp': timestamp,
            'confidence': (event1['confidence'] + event2['confidence']) / 2,
            'verified': True,
            'has_plate': bool(plate_event.get('plate'))
        }
        
        return merged
    
    def store_image(self, image_path: str, metadata: Dict) -> str:
        """
        Store image in GridFS
        Returns: GridFS file ID
        """
        try:
            with open(image_path, 'rb') as f:
                file_id = self.fs.put(f, filename=os.path.basename(image_path), **metadata)
            return f"gridfs://{file_id}"
        except Exception as e:
            print(f"❌ GridFS storage error: {e}")
            return image_path  # Fallback to file path
    
    def create_entry_session(self, merged_event: Dict) -> str:
        """
        Create new entry session from merged event
        Returns: session_id
        """
        try:
            plate = merged_event.get('plate')
            vehicle_data = merged_event['vehicle']
            has_plate = merged_event.get('has_plate', False)
            
            # Generate plate or temp_id
            if plate:
                identifier = plate
                # Check for duplicate entry
                existing = self.find_active_session(plate)
                if existing:
                    self.create_alert(
                        alert_type="DUPLICATE_ENTRY",
                        severity="MEDIUM",
                        plate=plate,
                        details={
                            "message": "Vehicle tried to enter while already inside",
                            "existing_session": existing['session_id']
                        }
                    )
                    return existing['session_id']
            else:
                # No plate - generate temp ID
                identifier = self.generate_temp_id(vehicle_data, merged_event['timestamp'])
            
            # Store images in GridFS
            gridfs_front = self.store_image(merged_event['image_front'], {
                "type": "entry_front",
                "plate": plate,
                "camera_id": merged_event['camera_front']
            })
            gridfs_rear = self.store_image(merged_event['image_rear'], {
                "type": "entry_rear",
                "plate": plate,
                "camera_id": merged_event['camera_rear']
            })
            
            # Generate session ID
            session_id = f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{identifier}"
            
            # Create session document
            session = {
                "session_id": session_id,
                "plate": plate,
                "temp_id": identifier if not plate else None,
                "has_plate": has_plate,
                "entry": {
                    "timestamp": merged_event['timestamp'],
                    "camera_front": merged_event['camera_front'],
                    "camera_rear": merged_event['camera_rear'],
                    "image_front": gridfs_front,
                    "image_rear": gridfs_rear,
                    "vehicle": vehicle_data,
                    "confidence": merged_event['confidence'],
                    "verified": merged_event['verified']
                },
                "exit": None,
                "duration_minutes": None,
                "status": "INSIDE",
                "metadata_match": None,
                "alerts": [],
                "requires_manual_review": not has_plate,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            # Flag for manual review if no plate
            if not has_plate:
                review_id = self.flag_for_manual_review(
                    plate=identifier,
                    image_path=gridfs_front,
                    confidence=merged_event['confidence'],
                    reason="No license plate detected on either camera"
                )
                session['alerts'].append(review_id)
            
            result = self.sessions.insert_one(session)
            
            status_emoji = "✅" if has_plate else "⚠️"
            print(f"{status_emoji} Entry session created: {session_id} [{identifier}]")
            
            return session_id
            
        except Exception as e:
            print(f"❌ Entry session creation error: {e}")
            return None
    
    def find_active_session(self, plate: Optional[str] = None, 
                           vehicle_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Find active (INSIDE) session for a plate or vehicle metadata
        Returns: session document or None
        """
        try:
            if plate:
                # Find by plate
                session = self.sessions.find_one({
                    "plate": plate,
                    "status": "INSIDE"
                })
                return session
            elif vehicle_data:
                # Find by metadata (for no-plate vehicles)
                return self._find_session_by_metadata(vehicle_data)
            else:
                return None
        except Exception as e:
            print(f"❌ Session lookup error: {e}")
            return None
    
    def _find_session_by_metadata(self, vehicle_data: Dict) -> Optional[Dict]:
        """
        Find active session by vehicle metadata (for no-plate vehicles)
        """
        try:
            # Get all active sessions without plates
            candidates = self.sessions.find({
                "status": "INSIDE",
                "has_plate": False
            })
            
            best_match = None
            best_score = 0
            
            for candidate in candidates:
                # Calculate match score
                score = self._calculate_metadata_match_score(
                    candidate['entry']['vehicle'],
                    vehicle_data
                )
                
                # Add time-based scoring (prefer recent entries)
                time_diff = (datetime.now() - candidate['entry']['timestamp']).total_seconds() / 60
                if time_diff < 30:  # < 30 minutes
                    score += 2
                elif time_diff < 60:  # < 60 minutes
                    score += 1
                
                if score > best_score and score >= 5:  # Require high confidence
                    best_score = score
                    best_match = candidate
            
            if best_match:
                print(f"✅ Found no-plate match: {best_match['temp_id']} (score: {best_score})")
            
            return best_match
            
        except Exception as e:
            print(f"❌ Metadata session lookup error: {e}")
            return None
    
    def complete_exit_session(self, merged_event: Dict) -> Optional[str]:
        """
        Complete exit for an active session from merged event
        Returns: session_id or None
        """
        try:
            plate = merged_event.get('plate')
            vehicle_data = merged_event['vehicle']
            has_plate = merged_event.get('has_plate', False)
            
            # Find active session (by plate or metadata)
            if plate:
                session = self.find_active_session(plate=plate)
            else:
                session = self.find_active_session(vehicle_data=vehicle_data)
            
            if not session:
                # No active session - create alert
                identifier = plate or self.generate_temp_id(vehicle_data, merged_event['timestamp'])
                self.create_alert(
                    alert_type="EXIT_WITHOUT_ENTRY",
                    severity="HIGH",
                    plate=identifier,
                    details={
                        "message": "Vehicle trying to exit without entry record",
                        "has_plate": has_plate
                    }
                )
                print(f"⚠️ Exit without entry: {identifier}")
                return None
            
            # Store exit images
            gridfs_front = self.store_image(merged_event['image_front'], {
                "type": "exit_front",
                "plate": plate,
                "camera_id": merged_event['camera_front']
            })
            gridfs_rear = self.store_image(merged_event['image_rear'], {
                "type": "exit_rear",
                "plate": plate,
                "camera_id": merged_event['camera_rear']
            })
            
            # Calculate duration
            entry_time = session['entry']['timestamp']
            exit_time = merged_event['timestamp']
            duration = (exit_time - entry_time).total_seconds() / 60  # minutes
            
            # Verify metadata match
            entry_vehicle = session['entry']['vehicle']
            metadata_match = self.verify_metadata_match(entry_vehicle, vehicle_data)
            
            # Check for plate mismatch (entry had plate, exit doesn't)
            plate_mismatch = session.get('has_plate') and not has_plate
            
            # Update session
            update_data = {
                "$set": {
                    "exit": {
                        "timestamp": exit_time,
                        "camera_front": merged_event['camera_front'],
                        "camera_rear": merged_event['camera_rear'],
                        "image_front": gridfs_front,
                        "image_rear": gridfs_rear,
                        "vehicle": vehicle_data,
                        "confidence": merged_event['confidence'],
                        "verified": merged_event['verified']
                    },
                    "duration_minutes": round(duration, 2),
                    "status": "COMPLETED" if (metadata_match and not plate_mismatch) else "ALERT",
                    "metadata_match": metadata_match,
                    "updated_at": datetime.now()
                }
            }
            
            # Create alerts for issues
            if not metadata_match:
                alert_id = self.create_alert(
                    alert_type="VEHICLE_MISMATCH",
                    severity="HIGH",
                    plate=plate or session['temp_id'],
                    details={
                        "message": "Vehicle metadata mismatch between entry and exit",
                        "entry_vehicle": entry_vehicle,
                        "exit_vehicle": vehicle_data,
                        "session_id": session['session_id']
                    }
                )
                update_data.setdefault("$push", {}).setdefault("alerts", []).append(alert_id)
            
            if plate_mismatch:
                alert_id = self.create_alert(
                    alert_type="PLATE_MISSING_ON_EXIT",
                    severity="HIGH",
                    plate=session['plate'],
                    details={
                        "message": "Plate visible on entry but not on exit",
                        "entry_plate": session['plate'],
                        "session_id": session['session_id']
                    }
                )
                update_data.setdefault("$push", {}).setdefault("alerts", []).append(alert_id)
            
            self.sessions.update_one(
                {"_id": session['_id']},
                update_data
            )
            
            identifier = plate or session.get('temp_id', 'UNKNOWN')
            status_emoji = "✅" if (metadata_match and not plate_mismatch) else "🚨"
            print(f"{status_emoji} Exit session completed: {session['session_id']} [{identifier}] - {duration:.1f} min")
            
            return session['session_id']
            
        except Exception as e:
            print(f"❌ Exit session completion error: {e}")
            return None
    
    def verify_metadata_match(self, entry_vehicle: Dict, exit_vehicle: Dict) -> bool:
        """
        Verify vehicle metadata matches between entry and exit
        Returns: True if match, False if mismatch
        """
        try:
            # Check critical fields
            make_match = entry_vehicle.get('make', '').lower() == exit_vehicle.get('make', '').lower()
            model_match = entry_vehicle.get('model', '').lower() == exit_vehicle.get('model', '').lower()
            color_match = entry_vehicle.get('color', '').lower() == exit_vehicle.get('color', '').lower()
            
            # All must match
            return make_match and model_match and color_match
            
        except Exception as e:
            print(f"⚠️ Metadata verification error: {e}")
            return False  # Fail-safe: flag as mismatch
    
    def create_alert(self, alert_type: str, severity: str, 
                    plate: str, details: Dict) -> str:
        """
        Create security alert
        Returns: alert_id
        """
        try:
            alert = {
                "type": alert_type,
                "severity": severity,  # LOW, MEDIUM, HIGH, CRITICAL
                "plate": plate,
                "details": details,
                "timestamp": datetime.now(),
                "resolved": False,
                "resolved_by": None,
                "resolved_at": None,
                "notes": []
            }
            
            result = self.alerts.insert_one(alert)
            alert_id = str(result.inserted_id)
            
            print(f"🚨 Alert created: {alert_type} [{severity}] - {plate}")
            
            return alert_id
            
        except Exception as e:
            print(f"❌ Alert creation error: {e}")
            return None
    
    def flag_for_manual_review(self, plate: str, image_path: str,
                               confidence: float, reason: str) -> str:
        """
        Flag detection for manual review
        Returns: review_id
        """
        try:
            review = {
                "plate": plate,
                "image_path": image_path,
                "confidence": confidence,
                "reason": reason,
                "timestamp": datetime.now(),
                "reviewed": False,
                "reviewer": None,
                "reviewed_at": None,
                "decision": None,  # APPROVED, REJECTED, CORRECTED
                "corrected_plate": None
            }
            
            result = self.manual_review.insert_one(review)
            review_id = str(result.inserted_id)
            
            print(f"⚠️ Flagged for manual review: {plate} (confidence: {confidence:.2f})")
            
            return review_id
            
        except Exception as e:
            print(f"❌ Manual review flagging error: {e}")
            return None
    
    def get_active_sessions(self, limit: int = 100) -> List[Dict]:
        """Get all active (INSIDE) sessions"""
        try:
            sessions = list(self.sessions.find(
                {"status": "INSIDE"},
                sort=[("entry.timestamp", DESCENDING)],
                limit=limit
            ))
            return sessions
        except Exception as e:
            print(f"❌ Active sessions query error: {e}")
            return []
    
    def get_session_history(self, plate: str, limit: int = 10) -> List[Dict]:
        """Get session history for a plate"""
        try:
            sessions = list(self.sessions.find(
                {"plate": plate},
                sort=[("entry.timestamp", DESCENDING)],
                limit=limit
            ))
            return sessions
        except Exception as e:
            print(f"❌ Session history query error: {e}")
            return []
    
    def get_unresolved_alerts(self, severity: Optional[str] = None) -> List[Dict]:
        """Get unresolved security alerts"""
        try:
            query = {"resolved": False}
            if severity:
                query["severity"] = severity
            
            alerts = list(self.alerts.find(
                query,
                sort=[("timestamp", DESCENDING)]
            ))
            return alerts
        except Exception as e:
            print(f"❌ Alerts query error: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection"""
        self.client.close()
