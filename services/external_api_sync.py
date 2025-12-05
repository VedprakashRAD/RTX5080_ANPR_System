"""
External API Sync Service
Forwards vehicle detection data to external surveillance API
"""

import requests
import os
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class ExternalAPISync:
    """Sync vehicle data to external surveillance API"""
    
    def __init__(self):
        """Initialize external API sync"""
        self.enabled = os.getenv("EXTERNAL_API_ENABLED", "false").lower() == "true"
        self.api_url = os.getenv("EXTERNAL_API_URL")
        self.api_token = os.getenv("EXTERNAL_API_TOKEN")
        
        if self.enabled:
            print(f"✅ External API sync enabled: {self.api_url}")
        else:
            print("⚠️ External API sync disabled")
    
    def is_enabled(self) -> bool:
        """Check if external API sync is enabled"""
        return self.enabled and self.api_url and self.api_token
    
    def sync_vehicle_data(self, data: Dict, image_path: str) -> bool:
        """
        Send vehicle data to external API
        
        Args:
            data: Vehicle detection data from ANPR
            image_path: Path to saved vehicle image
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            # Get camera ID and gate details
            camera_id = data.get('camera_id', 'UNKNOWN')
            
            # Prepare data for external API with camera ID and gate details
            payload = {
                'cameraId': camera_id,
                'cameraNumericId': self._get_camera_numeric_id(camera_id),
                'gateName': self._get_gate_name(camera_id),
                'registrationNumber': data.get('plate') or 'UNKNOWN',
                'movementType': self._get_movement_type(camera_id),
                'time': data.get('timestamp', datetime.now().isoformat()),
                'vehicleType': data.get('vehicle', {}).get('type', 'Car')
            }
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {self.api_token}'
            }
            
            # Prepare files
            files = {}
            if os.path.exists(image_path):
                files['image'] = open(image_path, 'rb')
            
            # Send request
            response = requests.post(
                self.api_url,
                headers=headers,
                data=payload,
                files=files,
                timeout=10
            )
            
            # Close file
            if files:
                files['image'].close()
            
            if response.status_code in [200, 201]:
                print(f"✅ External API sync successful: {payload['registrationNumber']}")
                return True
            else:
                print(f"⚠️ External API error {response.status_code}: {response.text}")
                return False
        
        except Exception as e:
            print(f"❌ External API sync failed: {e}")
            return False
    
    def _get_camera_numeric_id(self, camera_id: str) -> str:
        """
        Get numeric camera ID from camera identifier
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            Numeric camera ID
        """
        # Map camera IDs to numeric values
        camera_mapping = {
            '1': '1',
            '2': '2',
            '3': '3',
            '4': '4',
            'GATE1-ENTRY': '1',
            'GATE1-EXIT': '2',
            'GATE2-ENTRY': '3',
            'GATE2-EXIT': '4'
        }
        
        return camera_mapping.get(str(camera_id), camera_id)
    
    def _get_gate_name(self, camera_id: str) -> str:
        """
        Get gate name from camera ID
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            Gate name
        """
        # Map camera IDs to gate names
        gate_mapping = {
            '1': 'GATE1',
            '2': 'GATE1',
            '3': 'GATE2',
            '4': 'GATE2',
            'GATE1-ENTRY': 'GATE1',
            'GATE1-EXIT': 'GATE1',
            'GATE2-ENTRY': 'GATE2',
            'GATE2-EXIT': 'GATE2'
        }
        
        return gate_mapping.get(str(camera_id), 'UNKNOWN')
    
    def _get_movement_type(self, camera_id: str) -> str:
        """
        Determine movement type from camera ID
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            'IN' or 'OUT'
        """
        camera_id_upper = str(camera_id).upper()
        
        # Check for entry/exit in camera ID
        if 'ENTRY' in camera_id_upper or 'IN' in camera_id_upper or camera_id_upper in ['1', '3']:
            return 'IN'
        elif 'EXIT' in camera_id_upper or 'OUT' in camera_id_upper or camera_id_upper in ['2', '4']:
            return 'OUT'
        else:
            # Default to IN if unclear
            return 'IN'


# Example usage
if __name__ == "__main__":
    sync = ExternalAPISync()
    
    # Test data
    test_data = {
        'camera_id': '1',
        'plate': 'MH16RH7022',
        'vehicle': {
            'type': 'CAR',
            'color': 'White'
        },
        'timestamp': datetime.now().isoformat(),
        'confidence': 0.95
    }
    
    # Test sync
    if sync.is_enabled():
        result = sync.sync_vehicle_data(test_data, 'test_image.jpg')
        print(f"Sync result: {result}")
    else:
        print("External API sync is disabled")