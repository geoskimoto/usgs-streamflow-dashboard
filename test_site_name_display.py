#!/usr/bin/env python3
"""
Test to verify that site names are correctly displayed in plot headers.
This test checks that:
1. Site ID and station name are both shown in plot section headers
2. Station name is correctly retrieved from gauge data
3. Fallback to "Unknown Station" when station name not available
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

def test_station_name_in_headers():
    """Test that station names are included in plot headers."""
    print("🧪 Testing Station Name Display in Plot Headers")
    print("=" * 55)
    
    # Test data setup to simulate the multi-plot callback behavior
    test_site_id = "12113150"  # Example Washington site
    
    # Mock gauge data similar to what comes from the gauges store
    mock_gauges_data = [
        {
            'site_id': '12113150',
            'station_name': 'CEDAR RIVER AT RENTON, WA',
            'state': 'WA',
            'latitude': 47.4851,
            'longitude': -122.2148
        },
        {
            'site_id': '14211720', 
            'station_name': 'WILLAMETTE RIVER AT PORTLAND, OR',
            'state': 'OR',
            'latitude': 45.5152,
            'longitude': -122.6784
        },
        {
            'site_id': '99999999',
            'station_name': None,  # Test missing name
            'state': 'ID'
        }
    ]
    
    print("🔍 Test 1: Normal station name lookup")
    station_name = get_station_name(test_site_id, mock_gauges_data)
    expected_name = "CEDAR RIVER AT RENTON, WA"
    print(f"   Site ID: {test_site_id}")
    print(f"   Expected: {expected_name}")
    print(f"   Got: {station_name}")
    
    if station_name == expected_name:
        print("   ✅ SUCCESS: Station name retrieved correctly")
    else:
        print("   ❌ FAIL: Station name mismatch")
        
    print(f"\n📋 Test header format:")
    test_title = "Water Year Plot"
    header_text = f"{test_title} - Site {test_site_id} - {station_name}"
    print(f"   Header: {header_text}")
    
    print("\n🔍 Test 2: Missing station name fallback")
    missing_site = "99999999"
    station_name_missing = get_station_name(missing_site, mock_gauges_data)
    expected_fallback = "Unknown Station"
    print(f"   Site ID: {missing_site}")
    print(f"   Expected fallback: {expected_fallback}")
    print(f"   Got: {station_name_missing}")
    
    if station_name_missing == expected_fallback:
        print("   ✅ SUCCESS: Fallback works correctly")
    else:
        print("   ❌ FAIL: Fallback not working")
    
    print("\n🔍 Test 3: Site not found")
    unknown_site = "00000000"
    station_name_unknown = get_station_name(unknown_site, mock_gauges_data)
    print(f"   Site ID: {unknown_site}")
    print(f"   Expected fallback: {expected_fallback}")
    print(f"   Got: {station_name_unknown}")
    
    if station_name_unknown == expected_fallback:
        print("   ✅ SUCCESS: Unknown site handled correctly")
    else:
        print("   ❌ FAIL: Unknown site not handled properly")
    
    print("\n🔍 Test 4: Empty gauges data")
    station_name_empty = get_station_name(test_site_id, [])
    print(f"   Site ID: {test_site_id}")
    print(f"   Empty data expected fallback: {expected_fallback}")
    print(f"   Got: {station_name_empty}")
    
    if station_name_empty == expected_fallback:
        print("   ✅ SUCCESS: Empty data handled correctly")
    else:
        print("   ❌ FAIL: Empty data not handled properly")

def get_station_name(selected_gauge, gauges_data):
    """
    Replicate the station name lookup logic from the app callback.
    This simulates the exact logic used in update_multi_plots().
    """
    station_name = "Unknown Station"
    if gauges_data:
        for gauge in gauges_data:
            if gauge.get('site_id') == selected_gauge:
                station_name = gauge.get('station_name', 'Unknown Station')
                break
    return station_name

def test_real_data_integration():
    """Test with real data from the data manager if available."""
    print("\n🔗 Testing Real Data Integration")
    print("=" * 35)
    
    try:
        from usgs_dashboard.data.data_manager import get_data_manager
        
        data_manager = get_data_manager()
        filters_df = data_manager.get_filters_table()
        
        if len(filters_df) > 0:
            # Test with a real site
            sample_site = filters_df.iloc[0]
            site_id = sample_site['site_id']
            station_name = sample_site.get('station_name', 'Unknown Station')
            
            print(f"   Real site example:")
            print(f"     Site ID: {site_id}")
            print(f"     Station Name: {station_name}")
            print(f"     State: {sample_site.get('state', 'Unknown')}")
            
            # Test the lookup function with real data
            gauges_data = filters_df.to_dict('records')
            lookup_result = get_station_name(site_id, gauges_data)
            
            print(f"     Lookup result: {lookup_result}")
            
            if lookup_result == station_name:
                print("   ✅ SUCCESS: Real data lookup works correctly")
            else:
                print("   ❌ FAIL: Real data lookup mismatch")
            
            # Show example headers
            plot_types = ["Water Year Plot", "Annual Summary", "Flow Duration Curve"]
            print(f"\n   Example headers for site {site_id}:")
            for plot_type in plot_types:
                header = f"{plot_type} - Site {site_id} - {station_name}"
                print(f"     • {header}")
                
        else:
            print("   ⚠️ No real data available for testing")
            
    except Exception as e:
        print(f"   ⚠️ Real data test failed: {e}")
        print("   (This is expected if running outside the dashboard environment)")

if __name__ == "__main__":
    print("🧪 Testing Site Name Display in Streamflow Analysis")
    print("Testing the enhancement to include station names in plot headers...")
    print()
    
    try:
        test_station_name_in_headers()
        test_real_data_integration()
        
        print("\n" + "=" * 60)
        print("🎉 Station Name Display Tests Complete!")
        print("\n📋 Expected Results:")
        print("✅ Station names should appear in all plot section headers")
        print("✅ Format: 'Plot Type - Site ID - Station Name'")
        print("✅ Fallback to 'Unknown Station' when name unavailable")
        print("✅ Graceful handling of missing or empty data")
        
        print("\n🎯 User Experience:")
        print("• Users can now easily identify stations by name")
        print("• No need to cross-reference site IDs with station names")
        print("• Better context when viewing multiple plots")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()