#!/usr/bin/env python3
"""
Test the enhanced water year features in dashboard context
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from usgs_dashboard.components.viz_manager import VisualizationManager
from usgs_dashboard.data.data_manager import USGSDataManager

def test_dashboard_integration():
    """Test enhanced water year features in dashboard context."""
    
    print("🎨 Testing enhanced water year features in dashboard context...")
    
    # Initialize components like the dashboard would
    data_manager = USGSDataManager()
    viz_manager = VisualizationManager()
    
    # Test site
    site_id = '12113150'
    
    print(f"📥 Testing water year visualization for site {site_id}...")
    
    # Create water year plot through viz manager (like dashboard does)
    try:
        fig = viz_manager.create_plot(
            site_id=site_id, 
            plot_type='water_year',
            highlight_years=None  # Should default to current year
        )
        
        if fig is None:
            print("❌ No figure returned")
            return False
        
        print(f"✅ Figure created successfully")
        print(f"📊 Total traces: {len(fig.data)}")
        
        # Check for expected traces
        trace_names = [trace.name for trace in fig.data]
        print(f"📋 Trace names: {trace_names}")
        
        # Verify key features
        has_current_year = any('Water Year 2026' in name for name in trace_names)
        has_mean = any('Mean' in name for name in trace_names)
        has_median = any('Median' in name for name in trace_names)
        has_current_day = any('Current Day' in name for name in trace_names)
        
        # Check visibility
        all_yearly_visible = all(
            trace.visible == True 
            for trace in fig.data 
            if 'WY' in trace.name or 'Water Year' in trace.name
        )
        
        stat_traces_visible = all(
            trace.visible == True
            for trace in fig.data
            if trace.name in ['Mean', 'Median']
        )
        
        print(f"✅ Has current year highlighted: {has_current_year}")
        print(f"✅ Has mean line: {has_mean}")
        print(f"✅ Has median line: {has_median}")
        print(f"✅ Has current day marker: {has_current_day}")
        print(f"✅ All yearly traces visible: {all_yearly_visible}")
        print(f"✅ Statistics traces visible: {stat_traces_visible}")
        
        # Check x-axis is linear
        x_axis_linear = fig.layout.xaxis.type == 'linear'
        print(f"✅ X-axis is linear: {x_axis_linear}")
        
        success = (has_current_year and has_mean and has_median and 
                  has_current_day and all_yearly_visible and 
                  stat_traces_visible and x_axis_linear)
        
        return success
        
    except Exception as e:
        print(f"❌ Error creating plot: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dashboard_integration()
    if success:
        print("\n🎉 DASHBOARD INTEGRATION TEST PASSED!")
        print("   ✅ All enhanced features working in dashboard context")
        sys.exit(0)
    else:
        print("\n💥 DASHBOARD INTEGRATION TEST FAILED!")
        sys.exit(1)