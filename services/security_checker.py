"""
Security Checker for ANPR System

Implements security features:
- Plate swap detection
- Low confidence handling
- Duplicate entry detection
"""

from typing import Dict, Optional
from services.session_manager import SessionManager

class SecurityChecker:
    """Security validation for ANPR detections"""
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize security checker
        
        Args:
            session_manager: SessionManager instance
        """
        self.session_manager = session_manager
        
        # Thresholds
        self.low_confidence_threshold = 0.5
        self.critical_confidence_threshold = 0.3
    
    def check_plate_swap(self, plate: str, entry_vehicle: Dict, 
                        exit_vehicle: Dict) -> Dict:
        """
        Detect potential plate swap attack
        
        Scenario: Thief enters with valid plate on cheap car,
                 swaps plate to luxury car inside, tries to exit
        
        Returns:
            {
                'is_swap': bool,
                'severity': str,
                'details': dict
            }
        """
        # Compare vehicle metadata
        make_match = entry_vehicle.get('make', '').lower() == exit_vehicle.get('make', '').lower()
        model_match = entry_vehicle.get('model', '').lower() == exit_vehicle.get('model', '').lower()
        color_match = entry_vehicle.get('color', '').lower() == exit_vehicle.get('color', '').lower()
        type_match = entry_vehicle.get('type', '').lower() == exit_vehicle.get('type', '').lower()
        
        # Determine severity
        mismatches = []
        if not make_match:
            mismatches.append('make')
        if not model_match:
            mismatches.append('model')
        if not color_match:
            mismatches.append('color')
        if not type_match:
            mismatches.append('type')
        
        is_swap = len(mismatches) > 0
        
        # Severity levels
        if len(mismatches) >= 3:
            severity = "CRITICAL"  # Major mismatch
        elif len(mismatches) == 2:
            severity = "HIGH"  # Significant mismatch
        elif len(mismatches) == 1:
            severity = "MEDIUM"  # Minor mismatch
        else:
            severity = "LOW"  # No mismatch
        
        return {
            'is_swap': is_swap,
            'severity': severity,
            'mismatches': mismatches,
            'details': {
                'entry': entry_vehicle,
                'exit': exit_vehicle,
                'comparison': {
                    'make': f"{entry_vehicle.get('make')} → {exit_vehicle.get('make')}",
                    'model': f"{entry_vehicle.get('model')} → {exit_vehicle.get('model')}",
                    'color': f"{entry_vehicle.get('color')} → {exit_vehicle.get('color')}",
                    'type': f"{entry_vehicle.get('type')} → {exit_vehicle.get('type')}"
                }
            }
        }
    
    def check_confidence(self, plate: str, confidence: float, 
                        image_path: str) -> Dict:
        """
        Check detection confidence and flag for review if needed
        
        Returns:
            {
                'action': str,  # 'ACCEPT', 'REVIEW', 'REJECT'
                'reason': str,
                'review_id': str (if flagged)
            }
        """
        if confidence >= self.low_confidence_threshold:
            return {
                'action': 'ACCEPT',
                'reason': f'High confidence ({confidence:.2f})',
                'review_id': None
            }
        
        elif confidence >= self.critical_confidence_threshold:
            # Flag for manual review
            review_id = self.session_manager.flag_for_manual_review(
                plate=plate,
                image_path=image_path,
                confidence=confidence,
                reason=f"Low confidence detection ({confidence:.2f})"
            )
            
            return {
                'action': 'REVIEW',
                'reason': f'Low confidence ({confidence:.2f}) - flagged for review',
                'review_id': review_id
            }
        
        else:
            # Too low - reject
            return {
                'action': 'REJECT',
                'reason': f'Very low confidence ({confidence:.2f}) - rejected',
                'review_id': None
            }
    
    def check_duplicate_entry(self, plate: str) -> Dict:
        """
        Check if vehicle is trying to enter while already inside
        
        Returns:
            {
                'is_duplicate': bool,
                'existing_session': str (session_id if duplicate)
            }
        """
        active_session = self.session_manager.find_active_session(plate)
        
        if active_session:
            return {
                'is_duplicate': True,
                'existing_session': active_session['session_id'],
                'entry_time': active_session['entry']['timestamp']
            }
        
        return {
            'is_duplicate': False,
            'existing_session': None
        }
    
    def check_exit_without_entry(self, plate: str) -> Dict:
        """
        Check if vehicle is trying to exit without entry record
        
        Returns:
            {
                'has_entry': bool,
                'session_id': str (if found)
            }
        """
        active_session = self.session_manager.find_active_session(plate)
        
        if active_session:
            return {
                'has_entry': True,
                'session_id': active_session['session_id']
            }
        
        return {
            'has_entry': False,
            'session_id': None
        }
    
    def validate_entry(self, plate: str, vehicle_data: Dict, 
                      confidence: float, image_path: str) -> Dict:
        """
        Complete entry validation
        
        Returns:
            {
                'valid': bool,
                'action': str,
                'alerts': list,
                'review_id': str
            }
        """
        alerts = []
        review_id = None
        
        # Check 1: Confidence
        conf_check = self.check_confidence(plate, confidence, image_path)
        if conf_check['action'] == 'REJECT':
            return {
                'valid': False,
                'action': 'REJECT',
                'reason': conf_check['reason'],
                'alerts': alerts,
                'review_id': None
            }
        elif conf_check['action'] == 'REVIEW':
            review_id = conf_check['review_id']
            alerts.append('LOW_CONFIDENCE')
        
        # Check 2: Duplicate entry
        dup_check = self.check_duplicate_entry(plate)
        if dup_check['is_duplicate']:
            alerts.append('DUPLICATE_ENTRY')
        
        return {
            'valid': True,
            'action': conf_check['action'],
            'alerts': alerts,
            'review_id': review_id
        }
    
    def validate_exit(self, plate: str, vehicle_data: Dict,
                     confidence: float, image_path: str) -> Dict:
        """
        Complete exit validation
        
        Returns:
            {
                'valid': bool,
                'action': str,
                'alerts': list,
                'swap_detected': bool
            }
        """
        alerts = []
        
        # Check 1: Confidence
        conf_check = self.check_confidence(plate, confidence, image_path)
        if conf_check['action'] == 'REJECT':
            return {
                'valid': False,
                'action': 'REJECT',
                'reason': conf_check['reason'],
                'alerts': alerts,
                'swap_detected': False
            }
        elif conf_check['action'] == 'REVIEW':
            alerts.append('LOW_CONFIDENCE')
        
        # Check 2: Exit without entry
        entry_check = self.check_exit_without_entry(plate)
        if not entry_check['has_entry']:
            alerts.append('EXIT_WITHOUT_ENTRY')
            return {
                'valid': False,
                'action': 'ALERT',
                'reason': 'No entry record found',
                'alerts': alerts,
                'swap_detected': False
            }
        
        # Check 3: Plate swap
        session = self.session_manager.find_active_session(plate)
        if session:
            entry_vehicle = session['entry']['vehicle']
            swap_check = self.check_plate_swap(plate, entry_vehicle, vehicle_data)
            
            if swap_check['is_swap']:
                alerts.append('PLATE_SWAP')
                return {
                    'valid': True,  # Process but flag
                    'action': 'ALERT',
                    'reason': 'Vehicle metadata mismatch detected',
                    'alerts': alerts,
                    'swap_detected': True,
                    'swap_details': swap_check
                }
        
        return {
            'valid': True,
            'action': conf_check['action'],
            'alerts': alerts,
            'swap_detected': False
        }
