#!/usr/bin/env python3
"""
Test script to verify the filters table data can be loaded correctly.
"""

import sqlite3
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from usgs_dashboard.data.data_manager import get_data_manager

def test_filters_table():
    """Test loading data from filters table."""
    print("=" * 60)
    print("Testing Filters Table Data Loading")
    print("=" * 60)
    
    # Get data manager
    data_manager = get_data_manager()
    db_path = data_manager.cache_db
    
    print(f"\nDatabase path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    if not os.path.exists(db_path):
        print("❌ ERROR: Database not found!")
        return False
    
    try:
        # Connect and query
        conn = sqlite3.connect(db_path)
        
        # Get row count
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM filters")
        count = cursor.fetchone()[0]
        print(f"\n✅ Filters table has {count:,} rows")
        
        # Load as DataFrame
        filters_df = pd.read_sql_query('SELECT * FROM filters', conn)
        conn.close()
        
        print(f"✅ Loaded {len(filters_df):,} stations into DataFrame")
        print(f"\nColumns: {list(filters_df.columns)}")
        print(f"\nSample data (first 3 rows):")
        print(filters_df[['site_id', 'station_name', 'latitude', 'longitude', 'state']].head(3))
        
        # Check for required columns
        required_cols = ['site_id', 'station_name', 'latitude', 'longitude', 'state']
        missing = [col for col in required_cols if col not in filters_df.columns]
        
        if missing:
            print(f"\n❌ ERROR: Missing required columns: {missing}")
            return False
        else:
            print(f"\n✅ All required columns present")
        
        # Check data types
        print(f"\nData types:")
        for col in required_cols:
            print(f"  {col}: {filters_df[col].dtype}")
        
        # Convert to dict like the callback does
        gauges_data = filters_df.to_dict('records')
        print(f"\n✅ Converted to dict format: {len(gauges_data)} records")
        print(f"\nSample record:")
        print(gauges_data[0])
        
        print("\n" + "=" * 60)
        print("✅ TEST PASSED - Data loads correctly!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_filters_table()
    sys.exit(0 if success else 1)
