#!/usr/bin/env python3

"""
Test USGS National Map basemap integration.
Verify that the USGS basemap option works correctly in the dashboard.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

from usgs_dashboard.data.data_manager import USGSDataManager  
from usgs_dashboard.components.map_component import MapComponent
import pandas as pd

def test_usgs_basemap():
    """Test USGS National Map basemap functionality."""
    print("Testing USGS National Map basemap integration...")
    
    # Initialize components
    data_manager = USGSDataManager()
    map_component = MapComponent()
    
    try:
        # Get sample data
        print("Getting sample gauge data...")
        gauges_df = data_manager.get_filters_table()
        
        if gauges_df.empty:
            print("❌ No gauge data available for testing")
            return False
            
        print(f"✅ Found {len(gauges_df)} gauges for testing")
        
        # Test USGS National Map creation
        print("Testing USGS National Map creation...")
        
        # Create map with USGS basemap
        fig = map_component.create_gauge_map(
            gauges_df=gauges_df,
            map_style="usgs-national"
        )
        
        if fig is None:
            print("❌ Failed to create USGS National Map")
            return False
            
        print("✅ USGS National Map created successfully")
        
        # Verify map properties
        layout = fig.layout
        
        # Check if mapbox configuration exists
        if not hasattr(layout, 'mapbox'):
            print("❌ No mapbox configuration found")
            return False
            
        mapbox = layout.mapbox
        
        # Check for custom layers
        if not hasattr(mapbox, 'layers') or not mapbox.layers:
            print("❌ No custom layers found in USGS map")
            return False
            
        print("✅ Custom tile layers found")
        
        # Check layer source URL
        layer = mapbox.layers[0]
        expected_url = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSHydroCached/MapServer/tile/{z}/{y}/{x}"
        
        if layer.source != expected_url:
            print(f"❌ Incorrect tile URL. Expected: {expected_url}, Got: {layer.source}")
            return False
            
        print("✅ Correct USGS tile URL configured")
        
        # Check map style
        if mapbox.style != "white-bg":
            print(f"❌ Incorrect base style. Expected: white-bg, Got: {mapbox.style}")
            return False
            
        print("✅ Correct base map style configured")
        
        # Test empty map with USGS style
        print("Testing empty USGS map...")
        empty_fig = map_component._create_empty_map("usgs-national")
        
        if empty_fig is None:
            print("❌ Failed to create empty USGS map")
            return False
            
        # Verify empty map has USGS layers
        if not hasattr(empty_fig.layout, 'mapbox') or not empty_fig.layout.mapbox.layers:
            print("❌ Empty USGS map missing tile layers")
            return False
            
        print("✅ Empty USGS map created successfully")
        
        # Check traces exist on main map
        if not fig.data:
            print("❌ No map traces found")
            return False
            
        print(f"✅ Found {len(fig.data)} map traces")
        
        # Test map title
        expected_title_part = "USGS National Map"
        if expected_title_part not in str(layout.title):
            print(f"❌ Map title doesn't contain '{expected_title_part}'")
            return False
            
        print("✅ Map title includes USGS National Map reference")
        
        print("\n🎉 All USGS National Map basemap tests passed!")
        print("✅ USGS National Map integration is working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Error testing USGS basemap: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_usgs_basemap()
    sys.exit(0 if success else 1)