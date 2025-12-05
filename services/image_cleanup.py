"""
Image Cleanup Service
Automatically deletes images from saved_images directory 20 minutes after successful upload to external API
"""
import os
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ImageCleanupService:
    def __init__(self, image_dir="saved_images", cleanup_delay_minutes=20):
        """
        Initialize image cleanup service
        
        Args:
            image_dir: Directory containing saved images
            cleanup_delay_minutes: Delay in minutes before deleting uploaded images
        """
        self.image_dir = image_dir
        self.cleanup_delay_seconds = cleanup_delay_minutes * 60
        self.uploaded_images_file = os.path.join(image_dir, "uploaded_images.json")
        
        # Create directory if it doesn't exist
        Path(image_dir).mkdir(parents=True, exist_ok=True)
        
        # Load uploaded images tracking data
        self.uploaded_images = self._load_uploaded_images()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info(f"✅ Image cleanup service started (delay: {cleanup_delay_minutes} minutes)")
    
    def _load_uploaded_images(self):
        """Load uploaded images tracking data from file"""
        try:
            if os.path.exists(self.uploaded_images_file):
                with open(self.uploaded_images_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load uploaded images data: {e}")
        return {}
    
    def _save_uploaded_images(self):
        """Save uploaded images tracking data to file"""
        try:
            with open(self.uploaded_images_file, 'w') as f:
                json.dump(self.uploaded_images, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save uploaded images data: {e}")
    
    def mark_image_as_uploaded(self, image_path):
        """
        Mark an image as successfully uploaded to external API
        
        Args:
            image_path: Path to the image file
        """
        try:
            image_name = os.path.basename(image_path)
            upload_time = time.time()
            
            self.uploaded_images[image_name] = {
                'upload_time': upload_time,
                'scheduled_deletion': upload_time + self.cleanup_delay_seconds
            }
            
            self._save_uploaded_images()
            logger.debug(f"✅ Marked image as uploaded: {image_name}")
        except Exception as e:
            logger.error(f"❌ Failed to mark image as uploaded: {e}")
    
    def _cleanup_loop(self):
        """Background thread to periodically clean up old images"""
        while True:
            try:
                current_time = time.time()
                deleted_count = 0
                
                # Check for images that are ready for deletion
                images_to_remove = []
                for image_name, data in self.uploaded_images.items():
                    if current_time >= data['scheduled_deletion']:
                        image_path = os.path.join(self.image_dir, image_name)
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                                deleted_count += 1
                                logger.info(f"🗑️ Deleted uploaded image after 20min: {image_name}")
                            except Exception as e:
                                logger.warning(f"Failed to delete image {image_name}: {e}")
                        
                        # Mark for removal from tracking
                        images_to_remove.append(image_name)
                
                # Remove deleted images from tracking
                for image_name in images_to_remove:
                    del self.uploaded_images[image_name]
                
                if deleted_count > 0:
                    self._save_uploaded_images()
                    logger.info(f"🧹 Cleaned up {deleted_count} uploaded images")
                
                # Sleep for 1 minute before next check
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Image cleanup loop error: {e}")
                time.sleep(60)
    
    def get_uploaded_images_count(self):
        """Get count of currently tracked uploaded images"""
        return len(self.uploaded_images)
    
    def cleanup_old_tracking_data(self):
        """Remove tracking data for images that no longer exist"""
        try:
            current_time = time.time()
            images_to_remove = []
            
            for image_name, data in self.uploaded_images.items():
                # If image should have been deleted already but isn't tracked properly
                if current_time >= data['scheduled_deletion']:
                    image_path = os.path.join(self.image_dir, image_name)
                    if not os.path.exists(image_path):
                        images_to_remove.append(image_name)
            
            for image_name in images_to_remove:
                del self.uploaded_images[image_name]
            
            if images_to_remove:
                self._save_uploaded_images()
                logger.debug(f"🧹 Cleaned up {len(images_to_remove)} stale tracking entries")
                
        except Exception as e:
            logger.error(f"❌ Failed to clean up tracking data: {e}")

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create cleanup service
    cleanup_service = ImageCleanupService()
    
    # Simulate marking an image as uploaded
    test_image = "test_image.jpg"
    test_image_path = os.path.join("saved_images", test_image)
    
    # Create a test image
    Path(test_image_path).touch()
    
    # Mark as uploaded
    cleanup_service.mark_image_as_uploaded(test_image_path)
    
    print(f"Uploaded images count: {cleanup_service.get_uploaded_images_count()}")
    print("Service running... (Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping service...")