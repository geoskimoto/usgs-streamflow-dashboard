#!/usr/bin/env python3
"""
Test the cache fix to ensure datetime information is properly preserved.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from usgs_dashboard.data.data_manager import USGSDataManager
import pandas as pd
from datetime import datetime, timedelta

def test_cache_fix():
    """Test that the cache properly preserves datetime information."""
    
    print("🧪 Testing cache datetime preservation fix...")
    
    # Initialize data manager
    manager = USGSDataManager()
    
    # Test site
    site_id = '12113150'
    start_date = '2024-10-21'  # Match the actual cached date range
    end_date = '2025-10-21'
    
    print(f"📥 Downloading fresh data for site {site_id}...")
    
    # Force download fresh data (cache should be empty now)
    data = manager._download_validation_data(site_id, validation_years=1)
    
    if data is None or data.empty:
        print("❌ No data retrieved")
        return False
    
    print(f"✅ Downloaded {len(data)} records")
    print(f"📊 Data shape: {data.shape}")
    print(f"📅 Index type: {type(data.index)}")
    print(f"📋 Columns: {data.columns.tolist()}")
    
    # Check if index is DatetimeIndex
    if isinstance(data.index, pd.DatetimeIndex):
        print(f"✅ Proper DatetimeIndex with name: {data.index.name}")
        print(f"📅 Date range: {data.index.min()} to {data.index.max()}")
        print(f"🎯 Sample dates: {data.index[:3].tolist()}")
        
        # Check for 1970 corruption
        min_year = data.index.year.min()
        max_year = data.index.year.max()
        print(f"📅 Year range: {min_year} to {max_year}")
        
        if min_year == 1970 and max_year == 1970:
            print("❌ CORRUPTION DETECTED: All dates are in 1970")
            return False
        elif min_year >= 2020:
            print("✅ Dates look correct - no 1970 corruption")
            
            # Test loading from cache 
            print(f"🔄 Testing cache retrieval...")
            cached_data = manager._load_cached_streamflow_data(site_id, start_date, end_date)
            
            if cached_data is not None:
                print(f"✅ Cache retrieval successful: {len(cached_data)} records")
                
                if isinstance(cached_data.index, pd.DatetimeIndex):
                    cached_min_year = cached_data.index.year.min()
                    cached_max_year = cached_data.index.year.max()
                    print(f"📅 Cached year range: {cached_min_year} to {cached_max_year}")
                    
                    if cached_min_year == 1970:
                        print("❌ CACHE CORRUPTION: Cached data shows 1970 dates")
                        return False
                    else:
                        print("✅ CACHE SUCCESS: Proper dates preserved in cache")
                        return True
                else:
                    print("❌ Cache returned non-DatetimeIndex")
                    return False
            else:
                print("❌ Cache retrieval failed")
                return False
        else:
            print(f"⚠️ Unexpected year range: {min_year}-{max_year}")
            return False
    else:
        print(f"❌ Wrong index type: {type(data.index)}")
        return False

if __name__ == "__main__":
    success = test_cache_fix()
    if success:
        print("\n🎉 CACHE FIX TEST PASSED - Datetime preservation working correctly!")
        sys.exit(0)
    else:
        print("\n💥 CACHE FIX TEST FAILED - Still have datetime corruption issues")
        sys.exit(1)