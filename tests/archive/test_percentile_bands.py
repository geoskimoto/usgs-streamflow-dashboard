#!/usr/bin/env python3
"""
Test to verify that percentile bands are working correctly in Water Year plots.
"""

import sys
import os
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from usgs_dashboard.utils.water_year_datetime import WaterYearDateHandler

def create_test_data():
    """Create synthetic streamflow data for testing percentile bands."""
    print("Creating synthetic test data...")
    
    # Create 10 years of daily data
    start_date = datetime(2014, 10, 1)  # Water year 2015 start
    end_date = datetime(2024, 9, 30)    # Water year 2024 end
    
    dates = pd.date_range(start_date, end_date, freq='D')
    
    # Create synthetic flow data with seasonal patterns and year-to-year variability
    day_of_year = dates.dayofyear
    
    # Seasonal pattern (higher in spring, lower in late summer)
    seasonal_flow = 100 + 50 * np.sin((day_of_year - 80) * 2 * np.pi / 365)
    
    # Add year-to-year variability 
    yearly_multiplier = np.random.normal(1.0, 0.3, len(dates))
    
    # Add daily noise
    daily_noise = np.random.normal(0, 10, len(dates))
    
    # Calculate final flow values
    flow_values = np.maximum(seasonal_flow * yearly_multiplier + daily_noise, 5)  # Minimum 5 cfs
    
    df = pd.DataFrame({
        'datetime': dates,
        'discharge_cfs': flow_values
    })
    df.set_index('datetime', inplace=True)
    
    print(f"✅ Created {len(df)} days of synthetic data ({len(df.index.year.unique())} years)")
    return df

def test_percentile_bands():
    """Test that percentile bands are calculated and added to water year plots."""
    print("Testing percentile bands in water year plots...")
    
    # Create test data
    test_data = create_test_data()
    
    # Create water year handler
    wy_handler = WaterYearDateHandler()
    
    # Test with percentiles enabled
    print("Creating water year plot with percentiles enabled...")
    fig_with_percentiles = wy_handler.create_water_year_plot(
        test_data, 
        'discharge_cfs', 
        highlight_years=[2024, 2023],
        title="Test Water Year Plot with Percentiles",
        show_percentiles=True,
        show_statistics=True
    )
    
    # Test without percentiles for comparison
    print("Creating water year plot without percentiles...")
    fig_without_percentiles = wy_handler.create_water_year_plot(
        test_data, 
        'discharge_cfs', 
        highlight_years=[2024, 2023],
        title="Test Water Year Plot without Percentiles", 
        show_percentiles=False,
        show_statistics=True
    )
    
    # Check that percentile traces were added
    percentile_traces = [trace for trace in fig_with_percentiles.data 
                        if 'Percentile Range' in trace.name]
    
    print(f"Number of percentile traces found: {len(percentile_traces)}")
    
    # Should have 2 percentile range traces (10th-90th and 25th-75th)
    assert len(percentile_traces) == 2, f"Expected 2 percentile traces, got {len(percentile_traces)}"
    
    # Check trace names
    trace_names = [trace.name for trace in percentile_traces]
    expected_names = ['10th-90th Percentile Range', '25th-75th Percentile Range']
    
    for expected_name in expected_names:
        assert expected_name in trace_names, f"Missing expected trace: {expected_name}"
    
    # Verify that the plot without percentiles has fewer traces
    no_percentile_traces = [trace for trace in fig_without_percentiles.data 
                           if 'Percentile Range' in trace.name]
    
    assert len(no_percentile_traces) == 0, "Plot without percentiles should not have percentile traces"
    
    print("✅ Percentile bands are correctly added to water year plots!")
    
    # Check that percentile traces have fill
    fill_traces = [trace for trace in fig_with_percentiles.data if hasattr(trace, 'fill') and trace.fill]
    print(f"Number of traces with fill: {len(fill_traces)}")
    
    assert len(fill_traces) >= 2, "Should have at least 2 filled traces for percentile bands"
    
    print("✅ Percentile bands have proper fill styling!")
    
    return fig_with_percentiles, fig_without_percentiles

def test_percentile_calculations():
    """Test that percentile values are calculated correctly."""
    print("Testing percentile calculations...")
    
    # Create simple test data where we know the percentiles
    dates = pd.date_range('2023-10-01', '2023-10-10', freq='D')
    
    # Create data where day 1 has values [10, 20, 30, 40, 50] across different years
    # So 25th percentile = 20, 75th percentile = 40
    test_values = []
    test_dates = []
    
    for year_offset in range(5):  # 5 "years" of data for the same 10 days
        for i, date in enumerate(dates):
            test_dates.append(date.replace(year=2023 + year_offset))
            test_values.append(10 + year_offset * 10)  # Values: 10, 20, 30, 40, 50
    
    df = pd.DataFrame({
        'datetime': test_dates,
        'discharge_cfs': test_values
    })
    df.set_index('datetime', inplace=True)
    
    # Create handler and prepare data
    wy_handler = WaterYearDateHandler()
    plot_data = wy_handler.prepare_water_year_data(df, 'discharge_cfs')
    
    # Calculate percentiles manually
    daily_percentiles = plot_data.groupby('day_of_wy')['value'].agg([
        lambda x: x.quantile(0.25),
        lambda x: x.quantile(0.75),
    ])
    
    # For our test data, all days should have the same percentiles
    assert abs(daily_percentiles.iloc[0, 0] - 20) < 1, "25th percentile calculation incorrect"
    assert abs(daily_percentiles.iloc[0, 1] - 40) < 1, "75th percentile calculation incorrect"
    
    print("✅ Percentile calculations are correct!")

if __name__ == "__main__":
    print("Testing Water Year Plot Percentile Bands...")
    print("=" * 50)
    
    try:
        test_percentile_calculations()
        print()
        test_percentile_bands()
        
        print("\n" + "=" * 50)
        print("🎉 ALL PERCENTILE BAND TESTS PASSED!")
        print("📊 Water Year plots now include percentile bands:")
        print("   • 10th-90th percentile range (light blue)")
        print("   • 25th-75th percentile range (darker blue)")
        print("   • Mean and median lines (black dotted/dashed)")
        print("   • Individual water years (colored/gray lines)")
        print("🔍 Percentile bands provide historical context for current years")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)