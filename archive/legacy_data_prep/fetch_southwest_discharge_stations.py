#!/usr/bin/env python3
"""
Fetch all USGS streamflow stations in Southwest states (UT, AZ, CO) 
that have discharge data (parameter 00060).

This creates a clean, pre-filtered list for efficient data processing.

Usage:
    python fetch_southwest_discharge_stations.py

Output:
    - southwest_discharge_stations.csv: All stations in UT, AZ, CO with discharge
    - stations_summary.txt: Summary statistics
"""

import requests
import pandas as pd
import json
from datetime import datetime
import time

def get_state_discharge_stations():
    """
    Fetch all USGS stations in Southwest states with discharge data (parameter 00060).
    
    States: UT (Utah), AZ (Arizona), CO (Colorado)
    
    Returns:
        pd.DataFrame: DataFrame with station information including HUC classification
    """
    print("🔍 Fetching Southwest discharge stations by state...")
    print("States: UT, AZ, CO")
    print("Parameter: 00060 (Discharge/Streamflow)")
    
    # Target states
    states = ['UT', 'AZ', 'CO']
    all_stations = []
    
    # USGS Web Services URL for site information
    base_url = "https://waterservices.usgs.gov/nwis/site/"
    
    for state in states:
        print(f"\n📍 Processing {state}...")
        
        # Parameters for each state query - simplified approach
        params = {
            'format': 'rdb',  # Use RDB format instead of JSON
            'stateCd': state,  # State code
            'parameterCd': '00060',  # Discharge parameter
            'siteType': 'ST',  # Stream sites only
            'siteOutput': 'expanded'  # Get expanded site information
        }
        
        try:
            print(f"   📡 Querying USGS API for {state}...")
            print(f"      Parameter: 00060 (Discharge)")
            print(f"      Site Type: Stream (ST)")
            
            response = requests.get(base_url, params=params, timeout=60)
            response.raise_for_status()
            
            # Parse RDB format (tab-delimited)
            lines = response.text.strip().split('\n')
            
            # Skip comment lines (start with #)
            data_lines = [line for line in lines if not line.startswith('#')]
            
            if len(data_lines) < 2:  # Need at least header + data
                print(f"   ❌ No data found for {state}")
                continue
            
            # First line is header, second line is field formats (skip)
            headers = data_lines[0].split('\t')
            data_rows = data_lines[2:]  # Skip format line
            
            if not data_rows:
                print(f"   ❌ No sites found for {state}")
                continue
            
            print(f"   📊 Processing {len(data_rows)} sites in {state}...")
            
            state_stations = []
            for row in data_rows:
                try:
                    fields = row.split('\t')
                    if len(fields) < len(headers):
                        continue
                    
                    # Create dictionary from headers and fields
                    site_info = dict(zip(headers, fields))
                    
                    site_code = site_info.get('site_no', site_info.get('site_id', ''))
                    if not site_code:
                        continue
                    
                    # Extract data
                    huc_code = site_info.get('huc_cd', '')
                    station_name = site_info.get('station_nm', '')
                    latitude = site_info.get('dec_lat_va', site_info.get('lat_va', ''))
                    longitude = site_info.get('dec_long_va', site_info.get('long_va', ''))
                    county = site_info.get('county_cd', '')
                    drainage_area = site_info.get('drain_area_va', '')
                    
                    # Check if HUC 17 (Columbia River Basin)
                    is_huc17 = huc_code.startswith('17') if huc_code else False
                    huc_region = huc_code[:2] if huc_code and len(huc_code) >= 2 else ''
                    
                    station_data = {
                        'site_no': site_code,
                        'station_nm': station_name,
                        'latitude': latitude,
                        'longitude': longitude,
                        'state_cd': state,
                        'county_cd': county,
                        'huc_cd': huc_code,
                        'huc_code': huc_code,
                        'huc_region': huc_region,
                        'drainage_area': drainage_area,
                        'site_type': 'ST',
                        'active': 'Yes',
                        'basin': 'Southwest',
                        'is_huc17': is_huc17,
                        'has_discharge': True
                    }
                    
                    state_stations.append(station_data)
                    
                except Exception as e:
                    continue
            
            all_stations.extend(state_stations)
            print(f"   ✅ Found {len(state_stations)} discharge stations in {state}")
            time.sleep(1)  # Be polite to the API
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching {state} data: {e}")
            continue
    
    if not all_stations:
        print("\n❌ No stations found!")
        return None
    
    df = pd.DataFrame(all_stations)
    
    # Summary
    print("\n" + "="*60)
    print("📊 SOUTHWEST DISCHARGE STATIONS SUMMARY")
    print("="*60)
    print(f"Total Stations: {len(df)}")
    print(f"\nBy State:")
    for state, count in df['state_cd'].value_counts().items():
        print(f"  {state}: {count}")
    
    return df

def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("USGS Southwest Discharge Station Fetcher")
    print("="*60)
    
    # Fetch stations
    df = get_state_discharge_stations()
    
    if df is None or df.empty:
        print("\n❌ No data to save")
        return
    
    # Save all southwest stations
    output_file = 'data/southwest_discharge_stations.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved all Southwest stations to: {output_file}")
    
    # Save summary
    summary_file = 'data/southwest_stations_summary.txt'
    with open(summary_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write("SOUTHWEST DISCHARGE STATIONS SUMMARY\n")
        f.write("="*60 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Stations: {len(df)}\n\n")
        f.write("By State:\n")
        for state, count in df['state_cd'].value_counts().items():
            f.write(f"  {state}: {count}\n")
    
    print(f"✅ Saved summary to: {summary_file}")
    print("\n" + "="*60)
    print("✨ Complete!")
    print("="*60)

if __name__ == '__main__':
    main()
