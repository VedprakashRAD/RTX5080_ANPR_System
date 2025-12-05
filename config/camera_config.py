"""
Camera Configuration Manager
Loads and manages camera configurations
"""

import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CameraConfig:
    """Camera configuration manager"""
    
    def __init__(self, config_file: str = "config/cameras.json"):
        """Initialize camera config"""
        self.config_file = config_file
        self.cameras = []
        self.settings = {}
        self.load_config()
    
    def _substitute_env_vars(self, value):
        """Substitute environment variables in a string"""
        if isinstance(value, str):
            # Replace ${VAR} patterns with environment variable values
            import re
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)
            result = value
            for match in matches:
                env_value = os.getenv(match, '')
                result = result.replace('${' + match + '}', env_value)
            return result
        return value
    
    def load_config(self):
        """Load camera configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.cameras = config.get('cameras', [])
                    self.settings = config.get('settings', {})
                
                # Substitute environment variables in camera configurations
                for camera in self.cameras:
                    for key, value in camera.items():
                        camera[key] = self._substitute_env_vars(value)
                
                print(f"✅ Loaded {len(self.cameras)} cameras from {self.config_file}")
            else:
                print(f"⚠️ Config file not found: {self.config_file}")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
    
    def get_camera(self, camera_id: str) -> Optional[Dict]:
        """Get camera configuration by ID"""
        for camera in self.cameras:
            if camera['id'] == camera_id:
                return camera
        return None
    
    def get_all_cameras(self) -> List[Dict]:
        """Get all camera configurations"""
        return self.cameras
    
    def get_enabled_cameras(self) -> List[Dict]:
        """Get only enabled cameras"""
        return [cam for cam in self.cameras if cam.get('enabled', True)]
    
    def get_cameras_by_gate(self, gate: str) -> List[Dict]:
        """Get cameras for a specific gate"""
        return [cam for cam in self.cameras if cam.get('gate') == gate]
    
    def get_cameras_by_direction(self, direction: str) -> List[Dict]:
        """Get cameras by direction (ENTRY/EXIT)"""
        return [cam for cam in self.cameras if cam.get('direction') == direction]
    
    def get_rtsp_url(self, camera_id: str) -> Optional[str]:
        """Get RTSP URL for a camera"""
        camera = self.get_camera(camera_id)
        return camera.get('rtsp_url') if camera else None
    
    def is_camera_enabled(self, camera_id: str) -> bool:
        """Check if camera is enabled"""
        camera = self.get_camera(camera_id)
        return camera.get('enabled', False) if camera else False
    
    def get_setting(self, key: str, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)


# Example usage
if __name__ == "__main__":
    config = CameraConfig()
    
    print("\n📹 All Cameras:")
    for cam in config.get_all_cameras():
        print(f"  - {cam['id']}: {cam['name']} ({cam['location']})")
    
    print("\n🚪 Gate 1 Cameras:")
    for cam in config.get_cameras_by_gate("GATE1"):
        print(f"  - {cam['id']}: {cam['direction']}")
    
    print("\n➡️ Entry Cameras:")
    for cam in config.get_cameras_by_direction("ENTRY"):
        print(f"  - {cam['id']}: {cam['location']}")
    
    print("\n🔧 Settings:")
    print(f"  - Reconnect delay: {config.get_setting('reconnect_delay')}s")
    print(f"  - Timeout: {config.get_setting('timeout')}s")