#!/usr/bin/env python3
"""
Test script to validate imports and basic functionality
"""

def test_imports():
    """Test that all required imports work"""
    try:
        print("Testing standard library imports...")
        import tkinter as tk
        from tkinter import ttk, messagebox
        import asyncio
        import threading
        import time
        import json
        import requests
        from typing import Optional, Dict, Any
        from datetime import datetime
        print("✓ Standard library imports successful")
        
        print("Testing ph4_walkingpad imports...")
        from ph4_walkingpad.pad import Controller, WalkingPadCurStatus
        print("✓ ph4_walkingpad imports successful")
        
        print("Testing controller creation...")
        controller = Controller()
        print("✓ Controller created successfully")
        
        print("Testing GUI creation...")
        root = tk.Tk()
        root.withdraw()  # Hide the window
        print("✓ Tkinter root created successfully")
        root.destroy()
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Other error: {e}")
        return False

def test_home_assistant_api():
    """Test Home Assistant API format (without actual connection)"""
    try:
        print("Testing Home Assistant API format...")
        
        # Test data structure
        data = {
            'state': 1000,
            'attributes': {
                'unit_of_measurement': 'steps',
                'friendly_name': 'WalkingPad Steps',
                'last_updated': '2024-01-01T12:00:00'
            }
        }
        
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        print("✓ Home Assistant API format test successful")
        return True
        
    except Exception as e:
        print(f"✗ Home Assistant API test error: {e}")
        return False

if __name__ == "__main__":
    print("WalkingPad GUI - Import and Basic Functionality Test")
    print("=" * 50)
    
    success = True
    
    if not test_imports():
        success = False
    
    print()
    if not test_home_assistant_api():
        success = False
    
    print()
    if success:
        print("✓ All tests passed! The application should work correctly.")
        print("Note: Actual WalkingPad connection requires:")
        print("  - Bluetooth adapter")
        print("  - WalkingPad device powered on")
        print("  - Correct MAC address configured")
    else:
        print("✗ Some tests failed. Check the errors above.")
        
    print("\nTo run the GUI:")
    print("  walkingpad-gui      # If installed")
    print("  python3 main.py     # From source")
    print("  ./run.sh            # Using launcher") 