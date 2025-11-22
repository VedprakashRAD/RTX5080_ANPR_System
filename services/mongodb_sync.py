"""
MongoDB Sync Module for ALPR System
Handles asynchronous syncing of license plate records to MongoDB cloud storage
"""
import os
import logging
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MongoDBSync:
    def __init__(self):
        """Initialize MongoDB connection if configured"""
        self.enabled = False
        self.client = None
        self.collection = None
        
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri and mongo_uri.strip():
            try:
                from pymongo import MongoClient
                self.client = MongoClient(mongo_uri)
                db_name = os.getenv("MONGODB_DATABASE", "lpr_system")
                collection_name = os.getenv("MONGODB_COLLECTION", "vehicle_logs")
                self.collection = self.client[db_name][collection_name]
                self.enabled = True
                logger.info(f"✅ MongoDB connected: {db_name}.{collection_name}")
            except ImportError:
                logger.warning("⚠️ pymongo not installed. MongoDB sync disabled. Install: pip install pymongo")
            except Exception as e:
                logger.error(f"❌ MongoDB connection failed: {e}")
        else:
            logger.info("ℹ️ MongoDB not configured (MONGODB_URI not set)")
    
    def sync_record(self, record: Dict) -> bool:
        """
        Sync a license plate record to MongoDB
        
        Args:
            record: Dictionary containing plate data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in record:
                record['timestamp'] = datetime.now().isoformat()
            
            # Insert into MongoDB
            result = self.collection.insert_one(record)
            logger.info(f"☁️ Synced to MongoDB: {record.get('plate', 'UNKNOWN')} (ID: {result.inserted_id})")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB sync failed: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """Check if MongoDB sync is enabled"""
        return self.enabled
