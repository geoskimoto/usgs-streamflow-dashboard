#!/usr/bin/env python3
"""
Test script for real-time data visualization integration
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

from usgs_dashboard.data.data_manager import USGSDataManager
from usgs_dashboard.components.viz_manager import VisualizationManager

def test_realtime_visualization():
    """Test the enhanced visualization system with real-time data."""
    
    # Initialize managers
    data_manager = USGSDataManager()
    viz_manager = VisualizationManager()
    
    # Test with a site that should have real-time data
    # Using the site from our earlier testing
    site_id = "12113000"  # Green River near Auburn, WA
    
    print(f"Testing visualization for site: {site_id}")
    
    # Get daily data
    print("Getting daily streamflow data...")
    daily_data = data_manager.get_streamflow_data(site_id)
    if daily_data is None or daily_data.empty:
        print("❌ No daily data available")
        return
    
    print(f"✅ Daily data: {len(daily_data)} records from {daily_data.index.min()} to {daily_data.index.max()}")
    
    # Get real-time data
    print("Getting real-time data...")
    realtime_data = data_manager.get_realtime_data(site_id)
    if realtime_data is None or realtime_data.empty:
        print("⚠️ No real-time data available")
    else:
        print(f"✅ Real-time data: {len(realtime_data)} records from {realtime_data.index.min()} to {realtime_data.index.max()}")
    
    # Test visualization
    print("Creating visualization with both data types...")
    try:
        fig = viz_manager.create_streamflow_plot(
            site_id=site_id,
            streamflow_data=daily_data,
            plot_type='water_year',
            highlight_years=[2024],
            show_percentiles=True,
            show_statistics=True,
            data_manager=data_manager
        )
        
        # Check if the figure has multiple traces (daily + real-time)
        num_traces = len(fig.data)
        print(f"✅ Plot created with {num_traces} traces")
        
        # Look for real-time trace
        realtime_trace = None
        for trace in fig.data:
            if hasattr(trace, 'name') and 'real-time' in trace.name.lower():
                realtime_trace = trace
                break
        
        if realtime_trace:
            print(f"✅ Real-time trace found: '{realtime_trace.name}' with {len(realtime_trace.x)} points")
        else:
            print("⚠️ No real-time trace found in plot")
        
        print("✅ Enhanced visualization test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating visualization: {e}")
        return False

if __name__ == "__main__":
    test_realtime_visualization()