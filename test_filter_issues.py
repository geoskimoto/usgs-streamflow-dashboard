#!/usr/bin/env python3
"""
Comprehensive Test for USGS Dashboard Filter Issues

Tests the specific issues mentioned:
1. First filter works
2. Second filter change causes map to zoom way out
3. Large icon for selected station only 
4. Other stations fail to load
5. Need to refresh page to recover
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

import pandas as pd
import plotly.graph_objects as go
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.map_component import get_map_component
from usgs_dashboard.components.filter_panel import filter_component

def test_filter_sequence():
    """Test the specific sequence that causes issues."""
    print("🧪 Starting Filter Issue Diagnostic Test")
    print("=" * 60)
    
    # Initialize components
    data_manager = get_data_manager()
    map_component = get_map_component()
    
    print("📊 Loading initial data...")
    try:
        # Get initial gauge data
        initial_data = data_manager.get_filters_table()
        print(f"✅ Loaded {len(initial_data)} initial gauges")
        
        # Test 1: Initial map creation
        print("\n🗺️  Test 1: Initial Map Creation")
        initial_map = map_component.create_gauge_map(initial_data)
        print(f"   Map traces: {len(initial_map.data)}")
        print(f"   Map layout zoom: {initial_map.layout.mapbox.zoom}")
        print(f"   Map layout center: {initial_map.layout.mapbox.center}")
        
        # Test 2: First filter application (this should work)
        print("\n🔍 Test 2: First Filter (State = OR only)")
        filter_criteria_1 = {
            'states': ['OR']
        }
        
        # Apply filter using data manager
        filtered_data_1 = data_manager.apply_advanced_filters(initial_data, filter_criteria_1)
        print(f"   Filtered to {len(filtered_data_1)} Oregon gauges")
        
        # Create map with first filter
        map_1 = map_component.create_gauge_map(filtered_data_1)
        print(f"   Map 1 traces: {len(map_1.data)}")
        print(f"   Map 1 zoom: {map_1.layout.mapbox.zoom}")
        print(f"   Map 1 center: {map_1.layout.mapbox.center}")
        
        # Check for stored view state
        print(f"   Stored center: {map_component.last_center}")
        print(f"   Stored zoom: {map_component.last_zoom}")
        
        # Test 3: Second filter application (this is where issues occur)
        print("\n🔍 Test 3: Second Filter (State = WA only)")
        filter_criteria_2 = {
            'states': ['WA']  # Change from OR to WA
        }
        
        filtered_data_2 = data_manager.apply_advanced_filters(initial_data, filter_criteria_2)
        print(f"   Filtered to {len(filtered_data_2)} Washington gauges")
        
        # Create map with second filter - this is where zoom issues occur
        map_2 = map_component.create_gauge_map(filtered_data_2)
        print(f"   Map 2 traces: {len(map_2.data)}")
        print(f"   Map 2 zoom: {map_2.layout.mapbox.zoom}")
        print(f"   Map 2 center: {map_2.layout.mapbox.center}")
        
        # Check marker sizes (looking for "large icon" issue)
        print(f"   Checking marker sizes:")
        for i, trace in enumerate(map_2.data):
            if hasattr(trace, 'marker') and hasattr(trace.marker, 'size'):
                sizes = trace.marker.size if isinstance(trace.marker.size, list) else [trace.marker.size]
                print(f"     Trace {i}: sizes {min(sizes)} to {max(sizes)}")
        
        # Test 4: Station selection simulation
        print("\n🎯 Test 4: Station Selection Simulation")
        if len(filtered_data_2) > 0:
            selected_station = filtered_data_2.iloc[0]['site_id']
            print(f"   Selecting station: {selected_station}")
            
            # Create map with selection
            map_with_selection = map_component.create_gauge_map(
                filtered_data_2, 
                selected_gauge=selected_station
            )
            print(f"   Map with selection traces: {len(map_with_selection.data)}")
            
            # Check for selection highlight traces (these might be causing large icons)
            selection_traces = [trace for trace in map_with_selection.data 
                               if 'Selection' in str(trace.name) or 'Selected' in str(trace.name)]
            print(f"   Selection highlight traces: {len(selection_traces)}")
            
            for trace in selection_traces:
                if hasattr(trace, 'marker') and hasattr(trace.marker, 'size'):
                    print(f"     Selection trace size: {trace.marker.size}")
        
        # Test 5: Filter state persistence check
        print("\n💾 Test 5: Filter State Persistence")
        print(f"   Map component stored center: {map_component.last_center}")
        print(f"   Map component stored zoom: {map_component.last_zoom}")
        
        # Check if view state is being improperly preserved between different filter areas
        if len(filtered_data_1) > 0 and len(filtered_data_2) > 0:
            or_bounds = get_data_bounds(filtered_data_1)
            wa_bounds = get_data_bounds(filtered_data_2)
            
            print(f"   Oregon data bounds: {or_bounds}")
            print(f"   Washington data bounds: {wa_bounds}")
            
            # The issue might be that the map keeps Oregon's zoom/center when showing WA data
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

def get_data_bounds(data):
    """Calculate geographic bounds of data."""
    if len(data) == 0:
        return None
    
    return {
        'lat_min': data['latitude'].min(),
        'lat_max': data['latitude'].max(), 
        'lon_min': data['longitude'].min(),
        'lon_max': data['longitude'].max()
    }

def test_callback_behavior():
    """Test the callback behavior to identify the root cause."""
    print("\n🔄 Testing Callback Behavior")
    print("=" * 40)
    
    # Load the actual app callbacks to see how they handle state
    try:
        import sys
        sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots/usgs_dashboard')
        
        # Simulate the callback inputs that cause issues
        print("📝 Simulating callback sequence that causes issues...")
        
        # Initial state
        gauges_data = get_data_manager().get_filters_table()
        print(f"   Initial gauge count: {len(gauges_data)}")
        
        # First callback simulation (works fine)
        print("\n   🟢 First callback (OR filter):")
        filter_result_1 = simulate_filter_callback(
            gauges_data=gauges_data.to_dict('records'),
            map_style='open-street-map',
            status_values=['active', 'inactive'],
            state_values=['OR'],  # First filter
            drainage_range=[0, 100000],
            years_range=[1, 150],
            county_values=[],
            quality_values=['complete_coords'],
            selected_gauge=None
        )
        print(f"     Result: {filter_result_1['gauge_count']} gauges")
        
        # Second callback simulation (causes issues)
        print("\n   🔴 Second callback (WA filter):")
        filter_result_2 = simulate_filter_callback(
            gauges_data=gauges_data.to_dict('records'),
            map_style='open-street-map',
            status_values=['active', 'inactive'],
            state_values=['WA'],  # Second filter - different state
            drainage_range=[0, 100000],
            years_range=[1, 150],
            county_values=[],
            quality_values=['complete_coords'],
            selected_gauge=None
        )
        print(f"     Result: {filter_result_2['gauge_count']} gauges")
        
        # Third callback with selection (large icon issue)
        if filter_result_2['gauge_count'] > 0:
            print("\n   🎯 Third callback (station selection):")
            # Get a sample station ID from WA results
            wa_data = get_data_manager().apply_advanced_filters(gauges_data, {'states': ['WA']})
            if len(wa_data) > 0:
                selected_station = wa_data.iloc[0]['site_id']
                
                filter_result_3 = simulate_filter_callback(
                    gauges_data=gauges_data.to_dict('records'),
                    map_style='open-street-map',
                    status_values=['active', 'inactive'],
                    state_values=['WA'],
                    drainage_range=[0, 100000],
                    years_range=[1, 150],
                    county_values=[],
                    quality_values=['complete_coords'],
                    selected_gauge=selected_station  # This might cause large icon
                )
                print(f"     Result with selection: {filter_result_3['gauge_count']} gauges")
                print(f"     Selected station: {selected_station}")
        
    except Exception as e:
        print(f"❌ Callback test failed: {e}")
        import traceback
        traceback.print_exc()

def simulate_filter_callback(gauges_data, map_style, status_values, state_values, 
                           drainage_range, years_range, county_values, quality_values, 
                           selected_gauge):
    """Simulate the filter callback to identify issues."""
    
    data_manager = get_data_manager()
    map_component = get_map_component()
    
    # Convert data back to DataFrame
    all_gauges = pd.DataFrame(gauges_data)
    
    # Build filter criteria
    filter_criteria = {}
    if status_values:
        filter_criteria['status'] = status_values
    if state_values:
        filter_criteria['states'] = state_values
    if drainage_range and len(drainage_range) == 2:
        filter_criteria['drainage_range'] = drainage_range
    if years_range and len(years_range) == 2:
        filter_criteria['years_range'] = years_range
    if county_values:
        filter_criteria['counties'] = county_values
    if quality_values:
        filter_criteria['quality'] = quality_values
    
    # Apply filters
    try:
        filtered_gauges = data_manager.apply_advanced_filters(all_gauges, filter_criteria)
        
        # Create map
        fig = map_component.create_gauge_map(
            filtered_gauges,
            selected_gauge=selected_gauge,
            map_style=map_style
        )
        
        return {
            'gauge_count': len(filtered_gauges),
            'map_traces': len(fig.data),
            'map_zoom': fig.layout.mapbox.zoom if hasattr(fig.layout, 'mapbox') else None,
            'map_center': fig.layout.mapbox.center if hasattr(fig.layout, 'mapbox') else None,
            'success': True
        }
        
    except Exception as e:
        return {
            'gauge_count': 0,
            'error': str(e),
            'success': False
        }

if __name__ == "__main__":
    print("🔬 USGS Dashboard Filter Issue Diagnostic")
    print("Testing the specific filter problems reported...")
    print()
    
    # Run comprehensive tests
    test_filter_sequence()
    test_callback_behavior()
    
    print("\n" + "=" * 60)
    print("🏁 Test Complete!")
    print()
    print("📋 SUMMARY OF LIKELY ISSUES:")
    print("1. Map zoom state persisting between geographic regions")
    print("2. Selection highlight traces using oversized markers") 
    print("3. Filter state not properly resetting map view")
    print("4. Callback might be preserving wrong map center/zoom")
    print()
    print("🔧 RECOMMENDED FIXES:")
    print("1. Reset map center/zoom when data bounds change significantly")
    print("2. Reduce size of selection highlight markers")
    print("3. Clear map state between major filter changes")
    print("4. Add auto-fit bounds for filtered data")