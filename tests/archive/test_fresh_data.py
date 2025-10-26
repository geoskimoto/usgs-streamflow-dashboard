#!/usr/bin/env python3
"""
Test with fresh data (no cache) to isolate the data corruption issue
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from usgs_dashboard.data.data_manager import get_data_manager

def test_fresh_data():
    """Test with fresh data to see where corruption occurs"""
    print("Testing Fresh Data (No Cache)")
    print("=" * 40)
    
    try:
        data_manager = get_data_manager()
        
        # Clear cache first
        print("🗑️ Clearing cache...")
        data_manager.clear_cache()
        
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
        
        # Get fresh data (no cache)
        print(f"\n🆕 Fetching fresh data (no cache)...")
        fresh_data = data_manager.get_streamflow_data(site_id, use_cache=False)
        
        if fresh_data is None or fresh_data.empty:
            print("❌ No fresh data returned")
            return
            
        print(f"✅ Got {len(fresh_data)} records")
        
        # Analyze the fresh data
        print(f"\n🔍 Fresh data analysis:")
        print(f"   Index type: {type(fresh_data.index)}")
        print(f"   Index sample: {fresh_data.index[:5].tolist()}")
        
        if isinstance(fresh_data.index, pd.DatetimeIndex):
            unique_dates = fresh_data.index.nunique()
            date_range = f"{fresh_data.index.min()} to {fresh_data.index.max()}"
            unique_years = fresh_data.index.year.nunique()
            year_range = f"{fresh_data.index.year.min()} to {fresh_data.index.year.max()}"
            
            print(f"   ✅ Unique dates: {unique_dates}")
            print(f"   ✅ Date range: {date_range}")  
            print(f"   ✅ Unique years: {unique_years}")
            print(f"   ✅ Year range: {year_range}")
            
            if unique_years == 1 and fresh_data.index.year.min() == 1970:
                print(f"   ❌ CORRUPTION: All dates are 1970!")
            else:
                print(f"   ✅ Fresh data has proper date range!")
                
        print(f"\n📊 Data sample:")
        print(fresh_data.head())
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fresh_data()