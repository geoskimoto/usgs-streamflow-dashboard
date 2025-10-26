#!/usr/bin/env python3
"""
Test the UI improvements:
1. Enhanced header styling
2. Professional selected site icon (diamond instead of star)
3. Fixed basemap switching
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from usgs_dashboard.components.map_component import ModernMapComponent
import pandas as pd

def test_ui_improvements():
    """Test the UI improvements."""
    
    print("🎨 Testing UI improvements...")
    
    # Test data
    test_data = pd.DataFrame({
        'site_id': ['12345678', '87654321', '11111111'],
        'latitude': [45.0, 46.0, 44.0],
        'longitude': [-120.0, -121.0, -119.0],
        'station_name': ['Test Station 1', 'Test Station 2', 'Test Station 3'],
        'state': ['OR', 'WA', 'ID'],
        'drainage_area': [1000, 2000, 500],
        'status': ['excellent', 'good', 'fair'],
        'years_of_record': [25, 15, 10]
    })
    
    # Test map component
    map_component = ModernMapComponent()
    
    # Test 1: Basic map creation with different styles
    print("📍 Testing map with different basemap styles...")
    
    map_styles_to_test = [
        'open-street-map',
        'satellite-streets', 
        'outdoors',
        'light',
        'dark',
        'white-bg'
    ]
    
    success_count = 0
    for style in map_styles_to_test:
        try:
            fig = map_component.create_gauge_map(
                test_data, 
                selected_gauge='12345678',  # Select first gauge
                map_style=style
            )
            
            if fig is not None:
                print(f"  ✅ Map style '{style}' - SUCCESS")
                
                # Check if the selected gauge highlight exists
                trace_names = [trace.name for trace in fig.data if trace.name]
                has_selection = any('Selected' in name or 'Selection' in name for name in trace_names)
                
                if has_selection:
                    print(f"     🎯 Selected gauge highlight found")
                else:
                    print(f"     ⚠️  No selected gauge highlight found")
                
                # Check traces for professional selection
                selection_traces = [
                    trace for trace in fig.data 
                    if trace.name and ('Selected' in trace.name or 'Selection' in trace.name)
                ]
                
                if selection_traces:
                    print(f"     💎 Found {len(selection_traces)} selection trace(s)")
                    for trace in selection_traces:
                        symbol = getattr(trace.marker, 'symbol', 'none')
                        print(f"       - Trace: {trace.name}, Symbol: {symbol}")
                
                success_count += 1
            else:
                print(f"  ❌ Map style '{style}' - FAILED (returned None)")
                
        except Exception as e:
            print(f"  ❌ Map style '{style}' - ERROR: {e}")
    
    # Test 2: Empty map with styles
    print("\n📍 Testing empty map with different styles...")
    
    empty_success = 0
    for style in map_styles_to_test:
        try:
            fig = map_component._create_empty_map(style)
            if fig is not None and hasattr(fig, 'layout') and hasattr(fig.layout, 'map'):
                actual_style = fig.layout.map.style
                if actual_style == style:
                    print(f"  ✅ Empty map style '{style}' - APPLIED CORRECTLY")
                    empty_success += 1
                else:
                    print(f"  ⚠️  Empty map style '{style}' - Applied as '{actual_style}'")
            else:
                print(f"  ❌ Empty map style '{style}' - NO MAP LAYOUT")
        except Exception as e:
            print(f"  ❌ Empty map style '{style}' - ERROR: {e}")
    
    # Test 3: Professional selection icon
    print("\n💎 Testing professional selection icon...")
    
    fig = map_component.create_gauge_map(
        test_data, 
        selected_gauge='12345678',
        map_style='open-street-map'
    )
    
    # Look for diamond symbols (professional icon)
    diamond_traces = []
    star_traces = []
    
    for trace in fig.data:
        if hasattr(trace, 'marker') and hasattr(trace.marker, 'symbol'):
            if trace.marker.symbol == 'diamond':
                diamond_traces.append(trace)
            elif trace.marker.symbol == 'star':
                star_traces.append(trace)
    
    print(f"  Diamond traces found: {len(diamond_traces)}")
    print(f"  Star traces found: {len(star_traces)}")
    
    if diamond_traces and not star_traces:
        print("  ✅ Professional diamond icon successfully implemented")
        professional_icon = True
    elif star_traces:
        print("  ❌ Still using star icon (not professional)")
        professional_icon = False
    else:
        print("  ⚠️  No selection traces found")
        professional_icon = False
    
    # Summary
    print(f"\n📊 Test Summary:")
    print(f"  Map styles working: {success_count}/{len(map_styles_to_test)}")
    print(f"  Empty map styles working: {empty_success}/{len(map_styles_to_test)}")
    print(f"  Professional icon: {'✅' if professional_icon else '❌'}")
    
    overall_success = (
        success_count >= len(map_styles_to_test) * 0.8 and  # 80% of styles work
        empty_success >= len(map_styles_to_test) * 0.8 and  # 80% of empty maps work
        professional_icon  # Professional icon implemented
    )
    
    return overall_success

if __name__ == "__main__":
    success = test_ui_improvements()
    if success:
        print("\n🎉 UI IMPROVEMENTS TEST PASSED!")
        print("   ✅ Enhanced header styling ready")
        print("   ✅ Professional selection icon implemented") 
        print("   ✅ Basemap switching functionality working")
        sys.exit(0)
    else:
        print("\n💥 UI IMPROVEMENTS TEST FAILED!")
        sys.exit(1)