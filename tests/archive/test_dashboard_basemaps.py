#!/usr/bin/env python3

"""
Test the updated basemap dropdown options in the dashboard.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

from usgs_dashboard.data.data_manager import USGSDataManager
from usgs_dashboard.components.map_component import MapComponent

def test_dashboard_basemaps():
    """Test the new basemap options in the dashboard."""
    print("🗺️ Testing Dashboard Basemap Options")
    print("=" * 50)
    
    # Initialize components
    data_manager = USGSDataManager()
    map_component = MapComponent()
    
    # Get sample data
    gauges_df = data_manager.get_filters_table()
    print(f"📊 Testing with {len(gauges_df)} gauges")
    
    # Test all new dropdown options
    basemap_options = [
        ("usgs-national", "🏞️ USGS National Map"),
        ("open-street-map", "🗺️ OpenStreetMap"),
        ("carto-positron", "🌍 Carto Positron"),
        ("carto-darkmatter", "🌚 Carto Dark"),
        ("stamen-terrain", "🏔️ Stamen Terrain"),
        ("stamen-toner", "⚫ Stamen Toner"),
        ("stamen-watercolor", "🎨 Stamen Watercolor"),
        ("white-bg", "📰 White Background")
    ]
    
    successful_maps = []
    failed_maps = []
    
    for style_value, style_label in basemap_options:
        print(f"\n📍 Testing {style_label}...")
        
        try:
            # Create map using dashboard component
            fig = map_component.create_gauge_map(
                gauges_df=gauges_df,
                map_style=style_value
            )
            
            if fig is None:
                print(f"   ❌ Failed: Figure is None")
                failed_maps.append(style_label)
                continue
            
            # Check basic properties
            has_data = len(fig.data) > 0
            has_mapbox = hasattr(fig.layout, 'mapbox')
            
            if has_data and has_mapbox:
                print(f"   ✅ Success: {len(fig.data)} traces, mapbox configured")
                successful_maps.append(style_label)
                
                # Check for custom layers (USGS)
                if style_value == "usgs-national":
                    layers = getattr(fig.layout.mapbox, 'layers', [])
                    print(f"   🏔️ Custom layers: {len(layers)}")
                else:
                    print(f"   🗺️ Standard basemap: {fig.layout.mapbox.style}")
            else:
                print(f"   ❌ Failed: Missing data or mapbox config")
                failed_maps.append(style_label)
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            failed_maps.append(style_label)
    
    print(f"\n" + "=" * 50)
    print("📋 RESULTS SUMMARY")
    print("=" * 50)
    
    print(f"\n✅ Working basemaps ({len(successful_maps)}):")
    for style in successful_maps:
        print(f"   - {style}")
    
    if failed_maps:
        print(f"\n❌ Failed basemaps ({len(failed_maps)}):")
        for style in failed_maps:
            print(f"   - {style}")
    else:
        print(f"\n🎉 All basemaps working perfectly!")
    
    print(f"\n🚀 Ready to test in dashboard at http://localhost:8051")
    
    return len(successful_maps), len(failed_maps)

if __name__ == "__main__":
    test_dashboard_basemaps()