#!/usr/bin/env python3
"""
Test script to verify the data subset functionality works correctly.
This will test the subset selection without doing the full data load.
"""

import sys
import os
sys.path.append('./usgs_dashboard')

import pandas as pd
from usgs_dashboard.utils.config import SUBSET_CONFIG
from usgs_dashboard.data.data_manager import USGSDataManager

def create_sample_data():
    """Create sample gauge data for testing."""
    # Create sample data similar to what USGS returns
    states = ['OR', 'WA', 'ID']
    sample_data = []
    
    for i in range(500):  # Create 500 sample gauges
        state = states[i % 3]  # Distribute across states
        sample_data.append({
            'site_id': f'{12345678 + i:08d}',
            'station_name': f'Test Station {i+1}',
            'latitude': 44.0 + (i % 10) * 0.1,
            'longitude': -120.0 - (i % 10) * 0.1,
            'state': state,  # This matches the database schema
            'site_type': 'ST' if i % 4 == 0 else 'ST-CA',  # Mix of site types
            'begin_date': '1990-01-01' if i % 2 == 0 else '2010-01-01',  # Different start dates
            'end_date': '2024-10-01',
            'count_nu': str(10000 + i * 100),  # Simulated record count
            'is_active': True if i % 5 != 0 else False,  # Most active, some inactive
            'years_of_record': 20 + (i % 15),  # 20-34 years of record
            'drainage_area': 50 + (i % 100) * 10,  # Varying drainage areas
            'last_data_date': '2024-09-30' if i % 3 != 0 else '2023-12-31'  # Recent vs older data
        })
    
    return pd.DataFrame(sample_data)

def test_subset_functionality():
    """Test the subset functionality with sample data."""
    print("🧪 Testing Data Subset Functionality")
    print("=" * 60)
    
    # Show current configuration
    print("Current Subset Configuration:")
    for key, value in SUBSET_CONFIG.items():
        print(f"  {key}: {value}")
    print()
    
    # Create data manager instance
    manager = USGSDataManager()
    print("✅ Data manager created")
    
    # Create sample data
    sample_df = create_sample_data()
    print(f"✅ Created sample dataset with {len(sample_df)} gauges")
    
    # Show distribution of sample data
    print("\nSample Data Distribution:")
    print(f"  By State: {sample_df['state'].value_counts().to_dict()}")
    print(f"  Active: {sample_df['is_active'].sum()}, Inactive: {(~sample_df['is_active']).sum()}")
    print(f"  Years of Record: min={sample_df['years_of_record'].min()}, max={sample_df['years_of_record'].max()}")
    
    # Test subset methods
    print(f"\n🔍 Testing Subset Methods")
    print("-" * 40)
    
    # Test balanced subset
    try:
        balanced_subset = manager._select_balanced_subset(sample_df, 300)
        print(f"✅ Balanced subset: {len(balanced_subset)} sites selected")
        print(f"  State distribution: {balanced_subset['state'].value_counts().to_dict()}")
        print(f"  Active ratio: {balanced_subset['is_active'].mean():.2f}")
    except Exception as e:
        print(f"❌ Balanced subset failed: {e}")
    
    # Test quality subset
    try:
        quality_subset = manager._select_quality_subset(sample_df, 300)
        print(f"✅ Quality subset: {len(quality_subset)} sites selected")
        print(f"  State distribution: {quality_subset['state'].value_counts().to_dict()}")
        print(f"  Active ratio: {quality_subset['is_active'].mean():.2f}")
        print(f"  Avg years of record: {quality_subset['years_of_record'].mean():.1f}")
    except Exception as e:
        print(f"❌ Quality subset failed: {e}")
    
    # Test full apply_data_subset method
    try:
        final_subset = manager._apply_data_subset(sample_df)
        print(f"✅ Full subset method: {len(final_subset)} sites selected")
        print(f"  State distribution: {final_subset['state'].value_counts().to_dict()}")
        print(f"  Active ratio: {final_subset['is_active'].mean():.2f}")
    except Exception as e:
        print(f"❌ Full subset method failed: {e}")
    
    # Test subset status
    try:
        status = manager.get_subset_status()
        print(f"\n📊 Subset Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"❌ Subset status failed: {e}")
    
    print(f"\n🎉 Subset functionality test complete!")
    print(f"\n💡 To disable subset mode for production, set SUBSET_CONFIG['enabled'] = False in config.py")

if __name__ == "__main__":
    test_subset_functionality()