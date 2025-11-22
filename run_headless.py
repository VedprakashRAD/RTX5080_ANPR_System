#!/usr/bin/env python3
"""
Simple headless LPR runner
Usage: python run_headless.py
"""
import subprocess
import sys
import os

def main():
    print("🚀 Starting Headless LPR Service...")
    
    # Check if API server is running
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=3)
        print("✅ API server is running")
    except:
        print("❌ API server not running. Start with: python app.py")
        return
    
    # Start headless service
    try:
        subprocess.run([sys.executable, "lpr_headless.py"])
    except KeyboardInterrupt:
        print("\n👋 Headless service stopped")

if __name__ == "__main__":
    main()