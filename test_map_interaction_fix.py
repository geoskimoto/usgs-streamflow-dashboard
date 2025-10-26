#!/usr/bin/env python3
"""
Test Filter Issue Fixes - Validate the specific fixes implemented

Tests:
1. Auto-fit bounds working properly
2. Reduced selection highlight marker sizes
3. Map center/zoom adjusting for different geographic regions
4. No more "large icon" issues
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

import pandas as pd
import plotly.graph_objects as go
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.map_component import get_map_component

def test_auto_fit_bounds():
    """Test that auto-fit bounds adjusts map view for different regions."""
    print("🎯 Testing Auto-Fit Bounds Fix")
    print("=" * 50)
    
    # Initialize components
    data_manager = get_data_manager()
    map_component = get_map_component()
    
    # Get initial data
    initial_data = data_manager.get_filters_table()
    
    # Test Oregon data (southern region)
    print("🟢 Testing Oregon (Southern Region)")
    or_data = data_manager.apply_advanced_filters(initial_data, {'states': ['OR']})
    or_map = map_component.create_gauge_map(or_data, auto_fit_bounds=True)
    
    or_bounds = {
        'lat_min': or_data['latitude'].min(),
        'lat_max': or_data['latitude'].max(),
        'lon_min': or_data['longitude'].min(),
        'lon_max': or_data['longitude'].max()
    }
    
    or_center = or_map.layout.mapbox.center
    or_zoom = or_map.layout.mapbox.zoom
    
    print(f"   Oregon bounds: {or_bounds}")
    print(f"   Oregon map center: lat={or_center.lat:.3f}, lon={or_center.lon:.3f}")
    print(f"   Oregon map zoom: {or_zoom}")
    
    # Test Washington data (northern region)
    print("\n🔵 Testing Washington (Northern Region)")
    wa_data = data_manager.apply_advanced_filters(initial_data, {'states': ['WA']})
    wa_map = map_component.create_gauge_map(wa_data, auto_fit_bounds=True)
    
    wa_bounds = {
        'lat_min': wa_data['latitude'].min(),
        'lat_max': wa_data['latitude'].max(),
        'lon_min': wa_data['longitude'].min(),
        'lon_max': wa_data['longitude'].max()
    }
    
    wa_center = wa_map.layout.mapbox.center
    wa_zoom = wa_map.layout.mapbox.zoom
    
    print(f"   Washington bounds: {wa_bounds}")
    print(f"   Washington map center: lat={wa_center.lat:.3f}, lon={wa_center.lon:.3f}")
    print(f"   Washington map zoom: {wa_zoom}")
    
    # Verify the centers are different (fix working)
    lat_diff = abs(or_center.lat - wa_center.lat)
    lon_diff = abs(or_center.lon - wa_center.lon)
    
    print(f"\n📊 Center Difference Analysis:")
    print(f"   Latitude difference: {lat_diff:.3f} degrees")
    print(f"   Longitude difference: {lon_diff:.3f} degrees")
    
    if lat_diff > 1.0 or lon_diff > 1.0:
        print("   ✅ SUCCESS: Map centers are significantly different (auto-fit working)")
    else:
        print("   ❌ ISSUE: Map centers are too similar (auto-fit may not be working)")
    
    return lat_diff > 1.0 or lon_diff > 1.0

def test_selection_marker_sizes():
    """Test that selection highlight markers are reasonable sizes."""
    print("\n🎯 Testing Selection Marker Size Fix")
    print("=" * 50)
    
    # Initialize components
    data_manager = get_data_manager()
    map_component = get_map_component()
    
    # Get sample data
    sample_data = data_manager.get_filters_table().head(10)
    
    if len(sample_data) > 0:
        selected_station = sample_data.iloc[0]['site_id']
        
        print(f"🎯 Testing selection highlight for station: {selected_station}")
        
        # Create map with selection
        map_with_selection = map_component.create_gauge_map(
            sample_data, 
            selected_gauge=selected_station,
            auto_fit_bounds=True
        )
        
        print(f"   Total map traces: {len(map_with_selection.data)}")
        
        # Check marker sizes for all traces
        max_selection_size = 0
        for i, trace in enumerate(map_with_selection.data):
            if hasattr(trace, 'marker') and hasattr(trace.marker, 'size'):
                size = trace.marker.size
                trace_name = getattr(trace, 'name', f'Trace {i}')
                
                if isinstance(size, (list, tuple)):
                    size_desc = f"{min(size):.1f} to {max(size):.1f}"
                    trace_max_size = max(size)
                else:
                    size_desc = f"{size}"
                    trace_max_size = size
                
                print(f"   {trace_name}: size = {size_desc}")
                
                # Track selection highlight sizes
                if 'Selection' in trace_name or 'Selected' in trace_name:
                    max_selection_size = max(max_selection_size, trace_max_size)
                    
                    if trace_max_size > 30:
                        print(f"     ❌ ERROR: Selection size {trace_max_size} is too large! (should be ≤20)")
                    elif trace_max_size > 20:
                        print(f"     ⚠️  WARNING: Selection size {trace_max_size} is large (should be ≤20)")
                    else:
                        print(f"     ✅ Selection size {trace_max_size} is good (≤20)")
        
        return max_selection_size <= 20
    return True

def test_sequential_filter_changes():
    """Test the specific sequence that was causing issues."""
    print("\n🔄 Testing Sequential Filter Changes")
    print("=" * 50)
    
    # Initialize components
    data_manager = get_data_manager()
    map_component = get_map_component()
    
    # Get initial data
    initial_data = data_manager.get_filters_table()
    
    # Simulate the problematic sequence
    print("📝 Simulating the exact problem sequence:")
    
    # Step 1: Initial load (all states)
    print("\n   1️⃣ Initial load (all states)")
    all_map = map_component.create_gauge_map(initial_data, auto_fit_bounds=True)
    all_center = all_map.layout.mapbox.center
    all_zoom = all_map.layout.mapbox.zoom
    print(f"      Center: {all_center.lat:.3f}, {all_center.lon:.3f}, Zoom: {all_zoom}")
    
    # Step 2: First filter (Oregon) - should work fine
    print("\n   2️⃣ First filter change (Oregon only)")
    or_data = data_manager.apply_advanced_filters(initial_data, {'states': ['OR']})
    or_map = map_component.create_gauge_map(or_data, auto_fit_bounds=True)
    or_center = or_map.layout.mapbox.center
    or_zoom = or_map.layout.mapbox.zoom
    print(f"      Center: {or_center.lat:.3f}, {or_center.lon:.3f}, Zoom: {or_zoom}")
    print(f"      Gauges: {len(or_data)}")
    
    # Step 3: Second filter (Washington) - this was causing issues
    print("\n   3️⃣ Second filter change (Washington only) - Previously problematic")
    wa_data = data_manager.apply_advanced_filters(initial_data, {'states': ['WA']})
    wa_map = map_component.create_gauge_map(wa_data, auto_fit_bounds=True)
    wa_center = wa_map.layout.mapbox.center
    wa_zoom = wa_map.layout.mapbox.zoom
    print(f"      Center: {wa_center.lat:.3f}, {wa_center.lon:.3f}, Zoom: {wa_zoom}")
    print(f"      Gauges: {len(wa_data)}")
    
    # Step 4: Station selection (this was causing large icons)
    selection_size_ok = True
    if len(wa_data) > 0:
        print("\n   4️⃣ Station selection - Previously caused large icons")
        selected_station = wa_data.iloc[0]['site_id']
        selection_map = map_component.create_gauge_map(
            wa_data, 
            selected_gauge=selected_station, 
            auto_fit_bounds=True
        )
        print(f"      Selected station: {selected_station}")
        print(f"      Map traces: {len(selection_map.data)}")
        
        # Check for selection highlight sizes
        selection_traces = []
        for trace in selection_map.data:
            if 'Selection' in str(getattr(trace, 'name', '')) or 'Selected' in str(getattr(trace, 'name', '')):
                selection_traces.append(trace)
        
        print(f"      Selection highlight traces: {len(selection_traces)}")
        for trace in selection_traces:
            if hasattr(trace, 'marker') and hasattr(trace.marker, 'size'):
                size = trace.marker.size
                print(f"      Selection highlight size: {size} (was 35/22, should now be ≤20)")
                if size > 20:
                    selection_size_ok = False
    
    # Analyze if the fixes worked
    print(f"\n📊 Fix Validation:")
    
    # Check if map centers change appropriately
    or_wa_lat_diff = abs(or_center.lat - wa_center.lat)
    or_wa_lon_diff = abs(or_center.lon - wa_center.lon)
    
    print(f"   Oregon → Washington center change:")
    print(f"     Latitude: {or_wa_lat_diff:.3f}° (should be >1° for good auto-fit)")
    print(f"     Longitude: {or_wa_lon_diff:.3f}° (should be >1° for good auto-fit)")
    
    center_changed = or_wa_lat_diff > 1.0
    if center_changed:
        print(f"   ✅ Auto-fit bounds fix working: significant center change")
    else:
        print(f"   ❌ Auto-fit bounds may not be working: minimal center change")
    
    return center_changed and selection_size_ok

if __name__ == "__main__":
    print("🔧 Testing Filter Issue Fixes")
    print("Validating the fixes for:")
    print("- Map zoom/center persistence between regions")
    print("- Large selection highlight markers") 
    print("- Auto-fit bounds for filtered data")
    print()
    
    try:
        auto_fit_ok = test_auto_fit_bounds()
        selection_size_ok = test_selection_marker_sizes()
        sequential_ok = test_sequential_filter_changes()
        
        print("\n" + "=" * 60)
        print("🎉 Filter Fix Tests Complete!")
        
        print(f"\n📊 Results Summary:")
        print(f"   Auto-fit bounds: {'✅ PASS' if auto_fit_ok else '❌ FAIL'}")
        print(f"   Selection marker sizes: {'✅ PASS' if selection_size_ok else '❌ FAIL'}")
        print(f"   Sequential filter changes: {'✅ PASS' if sequential_ok else '❌ FAIL'}")
        
        all_passed = auto_fit_ok and selection_size_ok and sequential_ok
        
        if all_passed:
            print(f"\n🎉 ALL FIXES WORKING! The filter issues should be resolved.")
        else:
            print(f"\n⚠️  Some fixes may need adjustment.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()