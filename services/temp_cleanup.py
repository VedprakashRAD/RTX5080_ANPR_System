"""
Temp File Cleanup Module
Manages cleanup of temporary screenshot files to prevent disk space issues
"""
import os
import glob
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class TempFileCleanup:
    def __init__(self, temp_dir="temp_screenshots", max_age_hours=1):
        """
        Initialize temp file cleanup manager
        
        Args:
            temp_dir: Directory containing temporary files
            max_age_hours: Maximum age of files in hours before cleanup
        """
        self.temp_dir = temp_dir
        self.max_age_seconds = max_age_hours * 3600
        
        # Create directory if it doesn't exist
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
    
    def cleanup_old_files(self) -> int:
        """
        Remove files older than max_age_seconds
        
        Returns:
            Number of files deleted
        """
        try:
            current_time = time.time()
            deleted_count = 0
            
            # Find all image files in temp directory
            patterns = ['*.jpg', '*.jpeg', '*.png']
            files_to_check = []
            
            for pattern in patterns:
                files_to_check.extend(glob.glob(os.path.join(self.temp_dir, pattern)))
            
            for file_path in files_to_check:
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    
                    if file_age > self.max_age_seconds:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"🗑️ Deleted old temp file: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old temp files")
            
            return deleted_count
        except Exception as e:
            logger.error(f"❌ Temp file cleanup failed: {e}")
            return 0
    
    def cleanup_specific_file(self, filename: str) -> bool:
        """
        Delete a specific file
        
        Args:
            filename: Name of file to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            file_path = os.path.join(self.temp_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Deleted temp file: {filename}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete {filename}: {e}")
            return False
    
    def get_directory_size(self) -> tuple:
        """
        Get total size and file count of temp directory
        
        Returns:
            Tuple of (total_size_mb, file_count)
        """
        try:
            total_size = 0
            file_count = 0
            
            for pattern in ['*.jpg', '*.jpeg', '*.png']:
                files = glob.glob(os.path.join(self.temp_dir, pattern))
                file_count += len(files)
                for f in files:
                    total_size += os.path.getsize(f)
            
            size_mb = total_size / (1024 * 1024)
            return (size_mb, file_count)
        except Exception as e:
            logger.error(f"Failed to get directory size: {e}")
            return (0, 0)
