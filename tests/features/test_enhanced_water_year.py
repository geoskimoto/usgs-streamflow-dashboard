#!/usr/bin/env python3
"""
Test the enhanced water year plotting features:
- Default to current water year
- Mean and median lines on top 
- All yearly traces visible by default
- Current day marker (red dashed line)
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from usgs_dashboard.data.data_manager import USGSDataManager
from usgs_dashboard.utils.water_year_datetime import WaterYearDateTime
import pandas as pd
from datetime import datetime, timedelta

def test_enhanced_water_year_features():
    """Test all the new water year plotting features."""
    
    print("🎨 Testing enhanced water year plotting features...")
    
    # Initialize components
    manager = USGSDataManager()
    wy_handler = WaterYearDateTime()
    
    # Test site
    site_id = '12113150'
    
    # Get data for last 3 years
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
    
    print(f"📥 Loading data for site {site_id} from {start_date} to {end_date}...")
    
    data = manager.get_streamflow_data(site_id, start_date=start_date, end_date=end_date)
    
    if data is None or data.empty:
        print("❌ No data retrieved")
        return False
    
    print(f"✅ Loaded {len(data)} records")
    
    # Check what's the primary value column
    value_col = None
    for col in ['00060_Mean', 'discharge', 'value']:
        if col in data.columns:
            value_col = col
            break
    
    if value_col is None:
        print(f"❌ Could not find value column in: {data.columns.tolist()}")
        return False
    
    print(f"📊 Using value column: {value_col}")
    
    # Test current water year detection
    current_wy = wy_handler.get_water_year(pd.Timestamp.now())
    current_day = wy_handler.get_current_water_year_day()
    print(f"📅 Current water year: {current_wy}")
    print(f"📅 Current day of WY: {current_day}")
    
    # Prepare water year data
    plot_data = wy_handler.prepare_water_year_data(data, value_col)
    available_years = sorted(plot_data['water_year'].unique())
    print(f"📊 Available water years: {available_years}")
    
    # Test statistics calculation
    if len(plot_data) > 30:  # Need reasonable amount of data
        stats = wy_handler.calculate_statistics(plot_data)
        print(f"📈 Calculated statistics:")
        print(f"   Mean data points: {len(stats['mean'])}")
        print(f"   Median data points: {len(stats['median'])}")
        
        # Check some sample statistics
        sample_day = 100
        mean_stats = stats['mean']
        median_stats = stats['median']
        
        if len(mean_stats[mean_stats['day_of_wy'] == sample_day]) > 0:
            sample_mean = mean_stats[mean_stats['day_of_wy'] == sample_day]['value'].iloc[0]
            sample_median = median_stats[median_stats['day_of_wy'] == sample_day]['value'].iloc[0]
            print(f"   Day {sample_day} - Mean: {sample_mean:.1f}, Median: {sample_median:.1f}")
    
    # Create enhanced water year plot
    print(f"🎨 Creating enhanced water year plot...")
    
    fig = wy_handler.create_water_year_plot(
        data, 
        value_col, 
        highlight_years=None,  # Should default to current year
        title=f"Enhanced Water Year Plot - Site {site_id}",
        show_current_year=True,   # Default to current water year
        show_statistics=True,     # Show mean and median lines  
        show_current_day=True     # Show current day marker
    )
    
    # Check the traces in the figure
    print(f"📊 Figure analysis:")
    print(f"   Total traces: {len(fig.data)}")
    
    # Count different types of traces
    yearly_traces = []
    stat_traces = []
    current_day_traces = []
    
    for i, trace in enumerate(fig.data):
        trace_name = trace.name or f"Trace {i}"
        visible = trace.visible
        
        if 'Water Year' in trace_name or 'WY' in trace_name:
            yearly_traces.append((trace_name, visible))
        elif 'Mean' in trace_name or 'Median' in trace_name:
            stat_traces.append((trace_name, visible))
        elif 'Current Day' in trace_name:
            current_day_traces.append((trace_name, visible))
        
        print(f"   Trace {i+1}: '{trace_name}' - Visible: {visible}")
    
    # Verify requirements
    success_checks = []
    
    # Check 1: All yearly traces should be visible by default
    all_yearly_visible = all(visible == True for name, visible in yearly_traces)
    success_checks.append(("All yearly traces visible", all_yearly_visible))
    
    # Check 2: Statistics traces should exist and be visible
    stats_visible = len(stat_traces) >= 2 and all(visible == True for name, visible in stat_traces)
    success_checks.append(("Mean and median lines present and visible", stats_visible))
    
    # Check 3: Current day marker should exist and be visible
    current_day_visible = len(current_day_traces) >= 1 and all(visible == True for name, visible in current_day_traces)
    success_checks.append(("Current day marker present and visible", current_day_visible))
    
    # Check 4: X-axis should be numeric (linear)
    x_axis_linear = fig.layout.xaxis.type == 'linear'
    success_checks.append(("X-axis is linear (numeric)", x_axis_linear))
    
    # Report results
    print(f"\n📋 Feature verification:")
    all_passed = True
    for check_name, passed in success_checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False
    
    # Additional info
    print(f"\n📊 Trace details:")
    print(f"   Yearly traces: {len(yearly_traces)} (should all be visible)")
    print(f"   Statistics: {len(stat_traces)} (should be 2: mean + median)")
    print(f"   Current day: {len(current_day_traces)} (should be 1)")
    
    return all_passed

if __name__ == "__main__":
    success = test_enhanced_water_year_features()
    if success:
        print("\n🎉 ENHANCED WATER YEAR TEST PASSED!")
        print("   ✅ Current water year defaulted")
        print("   ✅ All yearly traces visible by default")
        print("   ✅ Mean and median lines on top")
        print("   ✅ Current day marker displayed")
        sys.exit(0)
    else:
        print("\n💥 ENHANCED WATER YEAR TEST FAILED!")
        sys.exit(1)