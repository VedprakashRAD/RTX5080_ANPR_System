import sqlite3
import os

DB_FILE = "lpr_logs.db"

def migrate_database():
    """Add missing columns to existing database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if columns exist and add them if missing
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN image_path TEXT")
        print("Added image_path column")
    except sqlite3.OperationalError:
        print("image_path column already exists")
    
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN roi_image_path TEXT")
        print("Added roi_image_path column")
    except sqlite3.OperationalError:
        print("roi_image_path column already exists")
    
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN api_response TEXT")
        print("Added api_response column")
    except sqlite3.OperationalError:
        print("api_response column already exists")
    
    conn.commit()
    conn.close()
    print("Database migration completed")

if __name__ == "__main__":
    migrate_database()
