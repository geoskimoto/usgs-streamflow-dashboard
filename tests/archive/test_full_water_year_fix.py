#!/usr/bin/env python3
"""
Test water year plotting with the cache fix to ensure no 1970 date corruption.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from usgs_dashboard.data.data_manager import USGSDataManager
from usgs_dashboard.utils.water_year_datetime import WaterYearDateTime
import pandas as pd

def test_water_year_plotting():
    """Test water year plotting with fresh data and cache fix."""
    
    print("🌊 Testing water year plotting with cache fix...")
    
    # Initialize components
    manager = USGSDataManager()
    wy_handler = WaterYearDateTime()
    
    # Test site
    site_id = '12113150'
    
    print(f"📥 Loading data for site {site_id}...")
    
    # Load streamflow data (last 2 years for quick test)
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=2*365)).strftime('%Y-%m-%d')
    
    data = manager.get_streamflow_data(site_id, start_date=start_date, end_date=end_date)
    
    if data is None or data.empty:
        print("❌ No data loaded")
        return False
    
    print(f"✅ Loaded {len(data)} records")
    print(f"📅 Index type: {type(data.index)}")
    
    if isinstance(data.index, pd.DatetimeIndex):
        min_year = data.index.year.min()
        max_year = data.index.year.max()
        print(f"📅 Year range: {min_year} to {max_year}")
        
        if min_year == 1970:
            print("❌ CORRUPTION DETECTED: Data shows 1970 dates")
            return False
        else:
            print("✅ Dates look correct - no 1970 corruption")
            
            # Test water year plotting
            print(f"📊 Testing water year plotting...")
            
            try:
                # Get first few years to test
                test_years = sorted(data.index.year.unique())[:3]
                print(f"🎯 Testing with years: {test_years}")
                
                for year in test_years:
                    fig = wy_handler.create_water_year_plot(
                        data=data,
                        site_info={'site_no': site_id, 'station_name': f'Test Site {site_id}'},
                        water_year=year,
                        highlighted_years=[],
                        title=f"Test Plot for WY {year}"
                    )
                    
                    if fig is None:
                        print(f"❌ Failed to create plot for WY {year}")
                        return False
                    
                    # Check that the plot has proper data
                    plot_data = fig.data[0]
                    x_values = plot_data.x
                    
                    if len(x_values) == 0:
                        print(f"❌ Empty plot for WY {year}")
                        return False
                    
                    # Check x-values are numeric (day of water year)
                    if all(isinstance(x, (int, float)) for x in x_values[:5]):
                        print(f"✅ WY {year} plot has proper numeric x-axis: {x_values[:5]}")
                    else:
                        print(f"❌ WY {year} plot has wrong x-axis type: {x_values[:5]}")
                        return False
                
                print("🎉 All water year plots created successfully!")
                return True
                
            except Exception as e:
                print(f"❌ Error during plotting: {e}")
                return False
    else:
        print(f"❌ Wrong index type: {type(data.index)}")
        return False

if __name__ == "__main__":
    success = test_water_year_plotting()
    if success:
        print("\n🎉 WATER YEAR PLOTTING TEST PASSED - No data corruption, plots working correctly!")
        sys.exit(0)
    else:
        print("\n💥 WATER YEAR PLOTTING TEST FAILED - Still have issues")
        sys.exit(1)