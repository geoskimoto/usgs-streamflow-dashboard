"""
Quick Dashboard Filter Test - Check if filtering works in the dashboard
"""

import sys
sys.path.append('/home/mrguy/Projects/streamflows/StackedLinePlots/usgs_dashboard')

from data.data_manager import get_data_manager
import pandas as pd

def test_dashboard_filtering():
    """Test the exact filtering logic used in the dashboard."""
    print("🧪 Testing Dashboard Filtering Logic...")
    
    # Get data manager and load data
    data_manager = get_data_manager()
    all_gauges = data_manager.load_regional_gauges(refresh=False)
    
    print(f"📊 Loaded {len(all_gauges)} total gauges")
    
    # Test the exact filter combinations from the dashboard
    
    # 1. Test with looser filters first
    print(f"\n🔄 Testing Looser Filters:")
    
    # Just active sites
    active_only = all_gauges[all_gauges['is_active'] == True]
    print(f"   - Active sites only: {len(active_only)}")
    
    # Just streams
    streams_only = all_gauges[all_gauges['site_type'].isin(['ST', 'ST-CA', 'ST-DCH', 'ST-TS'])]
    print(f"   - Stream sites (all types): {len(streams_only)}")
    
    # Just PNW states
    pnw_only = all_gauges[all_gauges['state'].isin(['OR', 'WA', 'ID'])]
    print(f"   - PNW states only: {len(pnw_only)}")
    
    # 2. Test the problematic combination
    print(f"\n🔄 Testing Default Dashboard Filters:")
    
    # Mimic the dashboard's default filters
    status_values = ['active']  # Active sites only
    site_type_values = ['ST', 'LK', 'SP']  # Surface water
    state_values = ['OR', 'WA', 'ID']  # All PNW states
    
    filtered_gauges = all_gauges.copy()
    
    # Status filter
    if 'active' in status_values and 'inactive' not in status_values:
        filtered_gauges = filtered_gauges[filtered_gauges['is_active'] == True]
        print(f"   - After status filter: {len(filtered_gauges)}")
    
    # Site type filter
    if site_type_values:
        site_filter = filtered_gauges['site_type'].isin(site_type_values)
        filtered_gauges = filtered_gauges[site_filter]
        print(f"   - After site type filter: {len(filtered_gauges)}")
    
    # State filter
    if state_values:
        filtered_gauges = filtered_gauges[filtered_gauges['state'].isin(state_values)]
        print(f"   - After state filter: {len(filtered_gauges)}")
    
    print(f"\n📊 Final Result: {len(filtered_gauges)} gauges")
    
    if len(filtered_gauges) > 0:
        print("✅ Dashboard filtering should now work!")
        
        # Show a sample
        sample = filtered_gauges.head(3)[['site_id', 'station_name', 'state', 'site_type', 'is_active']].to_dict('records')
        print(f"\n🔍 Sample results:")
        for i, gauge in enumerate(sample):
            print(f"   {i+1}. {gauge}")
    else:
        print("❌ Still getting 0 results")
        
        # Let's try inactive sites to see if there are more
        print(f"\n🔍 Trying with inactive sites included:")
        inactive_test = all_gauges[
            (all_gauges['site_type'].isin(['ST', 'LK', 'SP'])) &
            (all_gauges['state'].isin(['OR', 'WA', 'ID']))
        ]
        print(f"   - Surface water in PNW (any status): {len(inactive_test)}")
        
        if len(inactive_test) > 0:
            # Check status distribution
            status_dist = inactive_test['is_active'].value_counts()
            print(f"   - Status distribution: {status_dist.to_dict()}")
            print("💡 Suggestion: Try including inactive sites or improve activity detection")

if __name__ == "__main__":
    test_dashboard_filtering()
    print("\n🎉 Dashboard filter test complete!")
