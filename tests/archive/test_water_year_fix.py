#!/usr/bin/env python3
"""
Test script to verify the water year plotting fix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.viz_manager import get_visualization_manager

def test_water_year_plotting():
    """Test water year plotting with proper x-axis"""
    print("Testing Water Year Plotting Fix")
    print("=" * 40)
    
    try:
        # Get data manager and viz manager
        data_manager = get_data_manager()
        viz_manager = get_visualization_manager()
        
        # Get a sample site
        import sqlite3
        conn = sqlite3.connect(data_manager.cache_db)
        gauges_df = pd.read_sql_query('SELECT site_id FROM filters LIMIT 1', conn)
        conn.close()
        
        if len(gauges_df) == 0:
            print("❌ No gauges found")
            return
            
        site_id = gauges_df.iloc[0]['site_id']
        print(f"📍 Testing with site: {site_id}")
        
        # Get streamflow data
        streamflow_data = data_manager.get_streamflow_data(site_id)
        if streamflow_data is None or streamflow_data.empty:
            print("❌ No streamflow data")
            return
            
        print(f"✅ Got {len(streamflow_data)} records")
        
        # Test water year plot creation
        print(f"\n🧪 Testing water year plot creation...")
        
        try:
            fig = viz_manager.create_streamflow_plot(
                site_id=site_id,
                streamflow_data=streamflow_data,
                plot_type='water_year',
                highlight_years=[2024, 2025],
                show_percentiles=True,
                show_statistics=True
            )
            
            print(f"✅ Water year plot created successfully")
            
            # Check the figure structure
            print(f"\n📊 Plot analysis:")
            print(f"   Number of traces: {len(fig.data)}")
            
            # Check x-axis configuration
            if fig.layout.xaxis:
                axis_type = getattr(fig.layout.xaxis, 'type', 'auto')
                print(f"   X-axis type: {axis_type}")
                
                if hasattr(fig.layout.xaxis, 'tickvals') and fig.layout.xaxis.tickvals:
                    print(f"   X-axis tick values (sample): {fig.layout.xaxis.tickvals[:5]}")
                
                if hasattr(fig.layout.xaxis, 'ticktext') and fig.layout.xaxis.ticktext:
                    print(f"   X-axis tick text (sample): {fig.layout.xaxis.ticktext[:5]}")
            
            # Check if traces have proper x values
            if len(fig.data) > 0:
                first_trace = fig.data[0]
                if hasattr(first_trace, 'x') and first_trace.x:
                    x_values = list(first_trace.x)
                    print(f"   First trace x values (sample): {x_values[:10]}")
                    print(f"   X value range: {min(x_values)} to {max(x_values)}")
                    
                    # Check if values are numeric (not 1970 dates)
                    if all(isinstance(x, (int, float)) and 1 <= x <= 366 for x in x_values[:10]):
                        print(f"   ✅ X values are proper day-of-year numbers!")
                    else:
                        print(f"   ❌ X values still have date/datetime issues")
                        
            print(f"\n✅ Water year plot test completed!")
            
        except Exception as e:
            print(f"❌ Error creating water year plot: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_water_year_plotting()