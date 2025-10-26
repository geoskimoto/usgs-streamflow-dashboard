#!/usr/bin/env python3
"""
Test script for dynamic sidebar numbers
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import sqlite3
from usgs_dashboard.data.data_manager import get_data_manager

def test_dynamic_counts():
    """Test the dynamic counting functionality"""
    print("Testing Dynamic Sidebar Numbers")
    print("=" * 40)
    
    try:
        # Get data manager and load data
        data_manager = get_data_manager()
        
        # Load from cache/database
        db_path = data_manager.cache_db
        conn = sqlite3.connect(db_path)
        
        # Check if filters table exists and has data
        try:
            gauges_df = pd.read_sql_query('SELECT * FROM filters', conn)
            print(f"✅ Loaded {len(gauges_df)} gauges from database")
            
            if len(gauges_df) > 0:
                # Count by state
                state_counts = gauges_df['state'].value_counts()
                print("\n📊 State Distribution:")
                
                state_labels = {
                    'OR': '🌲 Oregon',
                    'WA': '🏔️ Washington', 
                    'ID': '⛰️ Idaho'
                }
                
                for state in ['OR', 'WA', 'ID']:
                    count = state_counts.get(state, 0)
                    label = f"{state_labels[state]} ({count} sites)"
                    print(f"   {label}")
                
                # Summary text
                summary = f"Filter {len(gauges_df)} USGS streamflow gauges (1910-present)"
                print(f"\n📋 Summary: {summary}")
                
            else:
                print("⚠️  No gauge data found in database")
                
        except Exception as e:
            print(f"⚠️  No filters table found: {e}")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_dynamic_counts()