#!/usr/bin/env python3
"""
Test script for dynamic site limit functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from usgs_dashboard.data.data_manager import USGSDataManager

def test_site_limits():
    """Test different site limit values"""
    print("Testing Dynamic Site Limit Functionality")
    print("=" * 50)
    
    # Initialize data manager
    dm = USGSDataManager()
    
    # Test with small limit (fast test)
    print("\n1. Testing with 5 sites (fast test):")
    try:
        gauges = dm.load_regional_gauges(refresh=True, max_sites=5)
        if hasattr(gauges, '__len__'):
            print(f"✅ Successfully loaded {len(gauges)} gauges")
        else:
            print(f"✅ Load completed (returned: {type(gauges)})")
    except Exception as e:
        print(f"❌ Error with 5 sites: {e}")
    
    # Test with medium limit 
    print("\n2. Testing with 50 sites (medium test):")
    try:
        gauges = dm.load_regional_gauges(refresh=False, max_sites=50)
        if hasattr(gauges, '__len__'):
            print(f"✅ Successfully loaded {len(gauges)} gauges")
        else:
            print(f"✅ Load completed (returned: {type(gauges)})")
    except Exception as e:
        print(f"❌ Error with 50 sites: {e}")
    
    # Test edge cases
    print("\n3. Testing edge cases:")
    
    # Test None (should use default)
    try:
        gauges = dm.load_regional_gauges(refresh=False, max_sites=None)
        print(f"✅ max_sites=None handled successfully")
    except Exception as e:
        print(f"❌ Error with max_sites=None: {e}")
    
    print("\n✅ Site limit functionality tests completed!")

if __name__ == "__main__":
    test_site_limits()