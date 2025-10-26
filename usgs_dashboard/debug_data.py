#!/usr/bin/env python3
"""
Debug script to check the actual data structure and column names
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.data_manager import USGSDataManager
import pandas as pd

print("=== DEBUGGING DATA STRUCTURE ===")

# Initialize data manager
data_manager = USGSDataManager()

try:
    # Load regional gauges
    print("Loading regional gauges...")
    gauges_df = data_manager.load_regional_gauges()
    
    print(f"✅ Loaded {len(gauges_df)} gauges")
    print(f"\n📊 Column names: {list(gauges_df.columns)}")
    
    if len(gauges_df) > 0:
        print(f"\n📋 Sample data (first 3 gauges):")
        for i in range(min(3, len(gauges_df))):
            sample = gauges_df.iloc[i]
            print(f"\n  Gauge {i+1}:")
            for col, val in sample.items():
                if col in ['site_id', 'station_name', 'site_tp_cd', 'state', 'status', 'agency_cd', 'drain_area_va', 'well_depth_va']:
                    print(f"    {col}: {val} (type: {type(val).__name__})")
        
        print(f"\n📈 Status distribution:")
        if 'status' in gauges_df.columns:
            print(gauges_df['status'].value_counts())
        else:
            print("❌ No 'status' column found!")
            
        # Check key filtering fields
        print(f"\n🔍 Filtering analysis:")
        if 'site_tp_cd' in gauges_df.columns:
            print(f"Site Types (site_tp_cd):")
            type_counts = gauges_df['site_tp_cd'].value_counts()
            for site_type, count in type_counts.head(10).items():
                print(f"  {site_type}: {count} sites")
        
        if 'agency_cd' in gauges_df.columns:
            print(f"Agencies:")
            print(gauges_df['agency_cd'].value_counts())
            
        if 'well_depth_va' in gauges_df.columns:
            well_sites = gauges_df[pd.notna(gauges_df['well_depth_va'])]['well_depth_va'].count()
            print(f"Sites with well depth data: {well_sites}")
            
        print(f"\n🌊 Site type analysis for filtering:")
        # Common USGS site type codes for filtering
        if 'site_tp_cd' in gauges_df.columns:
            st_sites = len(gauges_df[gauges_df['site_tp_cd'] == 'ST'])  # Stream
            gw_sites = len(gauges_df[gauges_df['site_tp_cd'] == 'GW'])  # Groundwater
            sp_sites = len(gauges_df[gauges_df['site_tp_cd'] == 'SP'])  # Spring
            lk_sites = len(gauges_df[gauges_df['site_tp_cd'] == 'LK'])  # Lake
            print(f"  Stream sites (ST): {st_sites}")
            print(f"  Groundwater sites (GW): {gw_sites}")
            print(f"  Spring sites (SP): {sp_sites}")
            print(f"  Lake sites (LK): {lk_sites}")
            
        print(f"\n🗺️ Geographic extent:")
        if 'latitude' in gauges_df.columns and 'longitude' in gauges_df.columns:
            print(f"  Latitude: {gauges_df['latitude'].min():.3f} to {gauges_df['latitude'].max():.3f}")
            print(f"  Longitude: {gauges_df['longitude'].min():.3f} to {gauges_df['longitude'].max():.3f}")
        else:
            print("❌ Missing latitude/longitude columns!")
            
        # Check for missing required columns for map
        required_cols = ['site_id', 'station_name', 'latitude', 'longitude', 'status', 'years_of_record']
        missing_cols = [col for col in required_cols if col not in gauges_df.columns]
        
        if missing_cols:
            print(f"\n❌ Missing required columns for map: {missing_cols}")
        else:
            print(f"\n✅ All required columns present for map rendering!")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
