#!/usr/bin/env python3
"""
Test to verify marker size and map center improvements.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from usgs_dashboard.components.map_component import MapComponent
from usgs_dashboard.utils.config import MAP_CENTER_LAT, MAP_CENTER_LON
import pandas as pd

def test_marker_sizes():
    """Test that marker sizes have been increased for better visibility."""
    print("Testing marker size improvements...")
    
    # Create sample data with different drainage areas
    sample_data = pd.DataFrame({
        'site_no': ['12345678', '87654321', '11111111'],
        'station_nm': ['Small Stream', 'Medium River', 'Large River'],
        'dec_lat_va': [46.0, 46.1, 46.2],
        'dec_long_va': [-117.0, -117.1, -117.2],
        'drainage_area': [10, 500, 5000],  # Small, medium, large
        'days_with_data': [100, 150, 200]
    })
    
    map_comp = MapComponent()
    processed_data = map_comp._prepare_map_data(sample_data, [], sample_data)
    
    # Check the size values
    min_size = processed_data['size_value'].min()
    max_size = processed_data['size_value'].max()
    
    print(f"Marker size range: {min_size:.1f} - {max_size:.1f} pixels")
    
    # Verify the new larger sizes (should be 10-25 range)
    assert min_size >= 10, f"Minimum marker size too small: {min_size}"
    assert max_size <= 25, f"Maximum marker size too large: {max_size}"
    assert max_size > min_size, "Size range not working properly"
    
    print("✅ Marker sizes are now larger and more visible!")
    return True

def test_map_center():
    """Test that map is now centered on broader Pacific Northwest."""
    print("Testing map center improvements...")
    
    print(f"New map center: {MAP_CENTER_LAT}°N, {MAP_CENTER_LON}°W")
    
    # Verify it's in the Pacific Northwest region
    assert 45 <= MAP_CENTER_LAT <= 47, f"Latitude should be in PNW range: {MAP_CENTER_LAT}"
    assert -120 <= MAP_CENTER_LON <= -115, f"Longitude should be in PNW range: {MAP_CENTER_LON}"
    
    # Create map component and verify initial center
    map_comp = MapComponent()
    assert map_comp.last_center['lat'] == MAP_CENTER_LAT
    assert map_comp.last_center['lon'] == MAP_CENTER_LON
    
    print("✅ Map is now centered on broader Pacific Northwest region!")
    return True

def test_empty_map_uses_new_center():
    """Test that empty maps use the new center."""
    print("Testing empty map with new center...")
    
    map_comp = MapComponent()
    empty_map = map_comp._create_empty_map()
    
    # Check that it uses the new center
    center_lat = empty_map.layout.mapbox.center.lat
    center_lon = empty_map.layout.mapbox.center.lon
    
    print(f"Empty map center: {center_lat}°N, {center_lon}°W")
    
    assert center_lat == MAP_CENTER_LAT, f"Empty map not using new center lat: {center_lat}"
    assert center_lon == MAP_CENTER_LON, f"Empty map not using new center lon: {center_lon}"
    
    print("✅ Empty maps use the new Pacific Northwest center!")
    return True

if __name__ == "__main__":
    print("Testing marker size and map center improvements...")
    print("=" * 55)
    
    try:
        test_marker_sizes()
        print()
        test_map_center()
        print()
        test_empty_map_uses_new_center()
        
        print("\n" + "=" * 55)
        print("🎉 ALL IMPROVEMENTS TESTED SUCCESSFULLY!")
        print("✨ Markers are now larger and more visible")
        print("🗺️  Map is centered on the broader Pacific Northwest")
        print("📍 Covers Oregon, Washington, and Idaho effectively")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)