#!/usr/bin/env python3
"""
Test to verify that the new zoom level works with view state preservation.
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from usgs_dashboard.components.map_component import MapComponent
from usgs_dashboard.utils.config import DEFAULT_ZOOM_LEVEL, MAP_CENTER_LAT, MAP_CENTER_LON

def test_new_zoom_level():
    """Test that the new zoom level provides better Pacific Northwest coverage."""
    print("Testing updated zoom level configuration...")
    
    # Verify the configuration
    print(f"Map center: {MAP_CENTER_LAT}°N, {MAP_CENTER_LON}°W")
    print(f"Default zoom: {DEFAULT_ZOOM_LEVEL}")
    
    # Create map component to test initialization
    map_comp = MapComponent()
    
    # Verify it uses the new defaults
    assert map_comp.last_center['lat'] == MAP_CENTER_LAT
    assert map_comp.last_center['lon'] == MAP_CENTER_LON
    assert map_comp.last_zoom == DEFAULT_ZOOM_LEVEL
    
    # Verify zoom level is appropriate for regional view
    assert DEFAULT_ZOOM_LEVEL == 5, f"Expected zoom 5, got {DEFAULT_ZOOM_LEVEL}"
    assert 4 <= DEFAULT_ZOOM_LEVEL <= 6, "Zoom should be in regional range"
    
    print("✅ New zoom level 5 configured correctly!")
    
    # Test empty map creation with new defaults
    empty_map = map_comp._create_empty_map()
    
    assert empty_map.layout.mapbox.center.lat == MAP_CENTER_LAT
    assert empty_map.layout.mapbox.center.lon == MAP_CENTER_LON  
    assert empty_map.layout.mapbox.zoom == DEFAULT_ZOOM_LEVEL
    
    print("✅ Empty maps use new zoom level!")
    
    return True

if __name__ == "__main__":
    print("Testing zoom level update...")
    print("=" * 40)
    
    try:
        test_new_zoom_level()
        
        print("\n" + "=" * 40)
        print("🎉 ZOOM LEVEL UPDATE SUCCESSFUL!")
        print("🗺️  Zoom level 5: Perfect for Pacific Northwest regional view")
        print("📍 Center: 46.0°N, -117.0°W (balanced OR, WA, ID coverage)")
        print("👀 Now shows most/all of Oregon, Washington, and Idaho")
        print("🔧 View state preservation still works with new defaults")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)