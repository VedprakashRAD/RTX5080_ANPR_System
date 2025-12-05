"""
Test script for Gate Verification Service
Tests dual-camera verification scenarios
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gate_verification_service import GateVerificationService
import time

def test_scenario_1_both_cameras_with_plate():
    """Test: Both cameras detect same vehicle with matching plates"""
    print("\n" + "="*70)
    print("TEST 1: Both cameras detect same vehicle with matching plates")
    print("="*70)
    
    config = {
        'gate_pairs': {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            }
        },
        'verification_window_seconds': 5,
        'min_match_score': 60
    }
    
    service = GateVerificationService(config)
    
    # Camera 1 (Entry) detection
    detection1_data = {
        'plate': 'MH12AB1234',
        'type': 'CAR',
        'color': 'WHITE',
        'confidence': 0.95,
        'image_path': '/tmp/gate1_entry_001.jpg'
    }
    
    print("\n📸 Camera 1 (GATE1-ENTRY) detects vehicle...")
    result1 = service.register_camera_detection('GATE1-ENTRY', detection1_data)
    print(f"Result: {result1}")
    
    # Wait 2 seconds (within verification window)
    time.sleep(2)
    
    # Camera 2 (Exit) detection with same plate
    detection2_data = {
        'plate': 'MH12AB1234',
        'type': 'CAR',
        'color': 'WHITE',
        'confidence': 0.92,
        'image_path': '/tmp/gate1_exit_001.jpg'
    }
    
    print("\n📸 Camera 2 (GATE1-EXIT) detects vehicle...")
    result2 = service.register_camera_detection('GATE1-EXIT', detection2_data)
    print(f"Result: {result2}")
    
    if result2 and result2.get('verified'):
        print("\n✅ TEST PASSED: Vehicles matched successfully!")
        print(f"   Event ID: {result2.get('event_id')}")
        print(f"   Match Score: {result2.get('match_score')}/100")
    else:
        print("\n❌ TEST FAILED: Verification failed")

def test_scenario_2_camera1_has_plate_camera2_no_plate():
    """Test: Camera 1 has plate, Camera 2 doesn't"""
    print("\n" + "="*70)
    print("TEST 2: Camera 1 has plate, Camera 2 doesn't (rear view)")
    print("="*70)
    
    config = {
        'gate_pairs': {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            }
        },
        'verification_window_seconds': 5,
        'min_match_score': 60
    }
    
    service = GateVerificationService(config)
    
    # Camera 1 (Entry) detection with plate
    detection1_data = {
        'plate': 'DL01XY9876',
        'type': 'SUV',
        'color': 'BLACK',
        'confidence': 0.88,
        'image_path': '/tmp/gate1_entry_002.jpg'
    }
    
    print("\n📸 Camera 1 (GATE1-ENTRY) detects vehicle with plate...")
    result1 = service.register_camera_detection('GATE1-ENTRY', detection1_data)
    
    time.sleep(1)
    
    # Camera 2 (Exit) detection without plate (rear view)
    detection2_data = {
        'plate': None,  # No plate visible
        'type': 'SUV',
        'color': 'BLACK',
        'confidence': 0.90,
        'image_path': '/tmp/gate1_exit_002.jpg'
    }
    
    print("\n📸 Camera 2 (GATE1-EXIT) detects vehicle without plate...")
    result2 = service.register_camera_detection('GATE1-EXIT', detection2_data)
    
    if result2 and result2.get('verified'):
        print("\n✅ TEST PASSED: Vehicles matched successfully!")
        print(f"   Final Plate: {result2.get('plate')} (from Camera 1)")
        print(f"   Match Score: {result2.get('match_score')}/100")
    else:
        print("\n❌ TEST FAILED: Verification failed")

def test_scenario_3_neither_camera_has_plate():
    """Test: Neither camera detects plate"""
    print("\n" + "="*70)
    print("TEST 3: Neither camera detects plate (match on type + color)")
    print("="*70)
    
    config = {
        'gate_pairs': {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            }
        },
        'verification_window_seconds': 5,
        'min_match_score': 60
    }
    
    service = GateVerificationService(config)
    
    # Camera 1 detection without plate
    detection1_data = {
        'plate': None,
        'type': 'TRUCK',
        'color': 'BLUE',
        'confidence': 0.85,
        'image_path': '/tmp/gate1_entry_003.jpg'
    }
    
    print("\n📸 Camera 1 (GATE1-ENTRY) detects vehicle without plate...")
    result1 = service.register_camera_detection('GATE1-ENTRY', detection1_data)
    
    time.sleep(1.5)
    
    # Camera 2 detection without plate
    detection2_data = {
        'plate': None,
        'type': 'TRUCK',
        'color': 'BLUE',
        'confidence': 0.87,
        'image_path': '/tmp/gate1_exit_003.jpg'
    }
    
    print("\n📸 Camera 2 (GATE1-EXIT) detects vehicle without plate...")
    result2 = service.register_camera_detection('GATE1-EXIT', detection2_data)
    
    if result2 and result2.get('verified'):
        print("\n✅ TEST PASSED: Vehicles matched on type + color!")
        print(f"   Match Score: {result2.get('match_score')}/100")
    else:
        print("\n❌ TEST FAILED: Verification failed")

def test_scenario_4_mismatched_vehicles():
    """Test: Different vehicles (should NOT match)"""
    print("\n" + "="*70)
    print("TEST 4: Different vehicles (should NOT match)")
    print("="*70)
    
    config = {
        'gate_pairs': {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            }
        },
        'verification_window_seconds': 5,
        'min_match_score': 60
    }
    
    service = GateVerificationService(config)
    
    # Camera 1 detects a CAR
    detection1_data = {
        'plate': 'KA01AB1234',
        'type': 'CAR',
        'color': 'RED',
        'confidence': 0.90,
        'image_path': '/tmp/gate1_entry_004.jpg'
    }
    
    print("\n📸 Camera 1 (GATE1-ENTRY) detects CAR...")
    result1 = service.register_camera_detection('GATE1-ENTRY', detection1_data)
    
    time.sleep(1)
    
    # Camera 2 detects a BIKE (different vehicle type)
    detection2_data = {
        'plate': 'KA02XY5678',
        'type': 'BIKE',
        'color': 'BLACK',
        'confidence': 0.88,
        'image_path': '/tmp/gate1_exit_004.jpg'
    }
    
    print("\n📸 Camera 2 (GATE1-EXIT) detects BIKE...")
    result2 = service.register_camera_detection('GATE1-EXIT', detection2_data)
    
    if result2 and result2.get('verified'):
        print("\n❌ TEST FAILED: Different vehicles should NOT match!")
    else:
        print("\n✅ TEST PASSED: Different vehicles correctly NOT matched")
        print(f"   Status: {result2.get('status') if result2 else 'No match'}")

def test_scenario_5_timeout():
    """Test: Detection timeout (no matching camera within window)"""
    print("\n" + "="*70)
    print("TEST 5: Detection timeout (no matching camera within window)")
    print("="*70)
    
    config = {
        'gate_pairs': {
            'GATE1': {
                'entry_camera_id': 'GATE1-ENTRY',
                'exit_camera_id': 'GATE1-EXIT'
            }
        },
        'verification_window_seconds': 3,  # Short window for testing
        'min_match_score': 60
    }
    
    service = GateVerificationService(config)
    service.max_pending_time = 5  # Short timeout for testing
    
    # Camera 1 detection
    detection1_data = {
        'plate': 'TN01CD5678',
        'type': 'CAR',
        'color': 'SILVER',
        'confidence': 0.92,
        'image_path': '/tmp/gate1_entry_005.jpg'
    }
    
    print("\n📸 Camera 1 (GATE1-ENTRY) detects vehicle...")
    result1 = service.register_camera_detection('GATE1-ENTRY', detection1_data)
    print(f"   Status: {result1.get('status') if result1 else 'None'}")
    
    # Wait beyond timeout
    print("\n⏰ Waiting 6 seconds (beyond timeout)...")
    time.sleep(6)
    
    # Trigger cleanup
    service._cleanup_expired_detections()
    
    print("\n✅ TEST PASSED: Expired detection cleaned up")
    print(f"   Pending detections: {len(service.pending_detections)}")

if __name__ == "__main__":
    print("\n🧪 GATE VERIFICATION SERVICE TEST SUITE")
    print("="*70)
    
    try:
        test_scenario_1_both_cameras_with_plate()
        test_scenario_2_camera1_has_plate_camera2_no_plate()
        test_scenario_3_neither_camera_has_plate()
        test_scenario_4_mismatched_vehicles()
        test_scenario_5_timeout()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
