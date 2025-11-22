#!/usr/bin/env python3
"""
Hailo-8L Hardware Verification Script
Run this after physically installing the Hailo AI HAT+
"""

import sys
import subprocess

def check_hailort_cli():
    """Check if hailortcli can detect the device"""
    print("🔍 Checking for Hailo hardware...")
    try:
        result = subprocess.run(['hailortcli', 'scan'], 
                              capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        
        if "not found" in output.lower():
            print("❌ Hailo device NOT detected")
            print("\n📋 Troubleshooting:")
            print("   1. Power off the Raspberry Pi")
            print("   2. Check that the HAT is firmly seated on GPIO pins")
            print("   3. Ensure adequate power supply (5V/5A)")
            print("   4. Power on and try again")
            return False
        else:
            print(f"✅ Hailo device detected!")
            print(f"   {output}")
            return True
    except subprocess.TimeoutExpired:
        print("⚠️  hailortcli scan timed out")
        return False
    except FileNotFoundError:
        print("❌ hailortcli not found. Run: sudo ldconfig")
        return False

def check_python_bindings():
    """Check if Python bindings work"""
    print("\n🐍 Checking Python bindings...")
    try:
        import hailo_platform as hailo
        print("✅ hailo_platform module imported successfully")
        
        # Try to get device info
        try:
            devices = hailo.Device.scan()
            if devices:
                print(f"✅ Found {len(devices)} Hailo device(s)")
                for dev in devices:
                    print(f"   - {dev}")
                return True
            else:
                print("⚠️  No Hailo devices found via Python API")
                return False
        except Exception as e:
            print(f"⚠️  Could not scan devices: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import hailo_platform: {e}")
        print("   Try: pip3 install --user /tmp/hailort/hailort/libhailort/bindings/python/platform")
        return False

def check_kernel_modules():
    """Check if kernel modules are loaded"""
    print("\n🔧 Checking kernel modules...")
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        if 'hailo' in result.stdout.lower():
            print("✅ Hailo kernel modules loaded")
            return True
        else:
            print("⚠️  No Hailo kernel modules found")
            print("   This is normal if using PCIe interface")
            return True  # Not critical
    except Exception as e:
        print(f"⚠️  Could not check modules: {e}")
        return True  # Not critical

def main():
    print("=" * 60)
    print("Hailo-8L AI HAT+ Verification")
    print("=" * 60)
    
    cli_ok = check_hailort_cli()
    kernel_ok = check_kernel_modules()
    python_ok = check_python_bindings()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"CLI Detection:    {'✅ PASS' if cli_ok else '❌ FAIL'}")
    print(f"Kernel Modules:   {'✅ PASS' if kernel_ok else '⚠️  WARNING'}")
    print(f"Python Bindings:  {'✅ PASS' if python_ok else '❌ FAIL'}")
    
    if cli_ok and python_ok:
        print("\n🎉 Hailo hardware is ready!")
        print("\nNext steps:")
        print("1. Download a VLM model in .hef format")
        print("2. Update vision_service.py to use Hailo")
        print("3. Test inference speed")
        return 0
    else:
        print("\n⚠️  Hardware setup incomplete")
        print("See hailo_setup_guide.md for installation instructions")
        return 1

if __name__ == "__main__":
    sys.exit(main())
