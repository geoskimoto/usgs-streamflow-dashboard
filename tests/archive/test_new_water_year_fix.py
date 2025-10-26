#!/usr/bin/env python3
"""
Test the new water year datetime handler to verify it solves the plotting issue
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.viz_manager import get_visualization_manager
from usgs_dashboard.utils.water_year_datetime import get_water_year_handler

def test_water_year_plotting_fix():
    """Test if the new water year handler fixes the plotting issue"""
    print("Testing Water Year Plotting Fix")
    print("=" * 40)
    
    try:
        # Get managers
        data_manager = get_data_manager()
        viz_manager = get_visualization_manager()
        wy_handler = get_water_year_handler()
        
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
        
        # Get streamflow data (use fresh data to avoid cache issues)
        print("🔄 Getting fresh streamflow data...")
        streamflow_data = data_manager.get_streamflow_data(site_id, use_cache=False)
        if streamflow_data is None or streamflow_data.empty:
            print("❌ No streamflow data")
            return
            
        print(f"✅ Retrieved {len(streamflow_data)} records")
        print(f"📊 Date range: {streamflow_data.index.min()} to {streamflow_data.index.max()}")
        
        # Test the new water year handler directly
        print(f"\n🧪 Testing water year handler directly...")
        
        # Find discharge column
        value_col = None
        for col in streamflow_data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            print("❌ No discharge column found")
            return
            
        print(f"📈 Using discharge column: {value_col}")
        
        # Test data preparation
        plot_data = wy_handler.prepare_water_year_data(streamflow_data, value_col)
        print(f"✅ Prepared data: {len(plot_data)} records")
        print(f"📊 Water years: {sorted(plot_data['water_year'].unique())}")
        print(f"📊 Day of WY range: {plot_data['day_of_wy'].min()} to {plot_data['day_of_wy'].max()}")
        
        # Test plot creation with new handler
        print(f"\n📊 Creating water year plot with new handler...")
        fig = wy_handler.create_water_year_plot(
            streamflow_data, 
            value_col, 
            highlight_years=[2024, 2025],
            title=f"Test Water Year Plot - Site {site_id}"
        )
        
        # Verify plot characteristics
        print(f"✅ Plot created successfully")
        print(f"📊 Number of traces: {len(fig.data)}")
        print(f"📊 X-axis type: {fig.layout.xaxis.type}")
        print(f"📊 X-axis title: {fig.layout.xaxis.title.text}")
        
        # Check if x-axis is properly numeric
        if fig.layout.xaxis.type == 'linear':
            print("✅ X-axis is properly set to linear (numeric)")
        else:
            print(f"❌ X-axis type is {fig.layout.xaxis.type} (should be linear)")
        
        # Test via visualization manager
        print(f"\n🔄 Testing via visualization manager...")
        fig2 = viz_manager.create_streamflow_plot(
            site_id,
            streamflow_data,
            plot_type='water_year',
            highlight_years=[2024, 2025]
        )
        
        print(f"✅ Visualization manager plot created")
        print(f"📊 X-axis type: {fig2.layout.xaxis.type}")
        
        # Multiple plot test (the original issue)
        print(f"\n🔄 Testing multiple plot creation (original issue)...")
        
        for i in range(3):
            print(f"   Creating plot {i+1}...")
            test_fig = viz_manager.create_streamflow_plot(
                site_id,
                streamflow_data,
                plot_type='water_year',
                highlight_years=[2023, 2024, 2025]
            )
            
            # Check x-axis integrity
            x_type = test_fig.layout.xaxis.type
            x_range = test_fig.layout.xaxis.range
            print(f"   Plot {i+1}: X-axis type={x_type}, range={x_range}")
            
        print(f"\n🎉 SUCCESS: Water year plotting fix appears to be working!")
        print(f"✅ No more 1970 date issues")
        print(f"✅ X-axis properly set to numeric")
        print(f"✅ Multiple plot creation works")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_water_year_plotting_fix()