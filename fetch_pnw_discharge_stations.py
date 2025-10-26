#!/usr/bin/env python3
"""
Fetch all USGS streamflow stations in Pacific Northwest states (OR, WA, ID, MT, NV) 
that have discharge data (parameter 00060).

This creates a clean, pre-filtered list for efficient data processing, eliminating 
the need to ping 2800+ sites individually. Also identifies HUC 17 stations for 
default filtering in the dashboard.

Usage:
    python get_huc17_discharge_stations.py

Output:
    - all_pnw_discharge_stations.csv: All stations in OR, WA, ID, MT, NV with discharge
    - huc17_discharge_stations.csv: HUC 17 stations only (for default dashboard view)
    - stations_summary.txt: Summary statistics
"""

import requests
import pandas as pd
import json
from datetime import datetime
import time

def get_state_discharge_stations():
    """
    Fetch all USGS stations in Pacific Northwest states with discharge data (parameter 00060).
    
    States: OR (Oregon), WA (Washington), ID (Idaho), MT (Montana), NV (Nevada)
    
    Returns:
        pd.DataFrame: DataFrame with station information including HUC classification
    """
    print("🔍 Fetching Pacific Northwest discharge stations by state...")
    print("States: OR, WA, ID, MT, NV")
    print("Parameter: 00060 (Discharge/Streamflow)")
    
    # Target states
    states = ['OR', 'WA', 'ID', 'MT', 'NV']
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
                    
                    site_code = site_info.get('site_no', '')
                    if not site_code:
                        continue
                    
                    # Extract data
                    huc_code = site_info.get('huc_cd', '')
                    station_name = site_info.get('station_nm', '')
                    latitude = site_info.get('dec_lat_va', '')
                    longitude = site_info.get('dec_long_va', '')
                    drainage_area = site_info.get('drain_area_va', '')
                    
                    # Convert to proper types
                    try:
                        lat = float(latitude) if latitude else None
                    except (ValueError, TypeError):
                        lat = None
                        
                    try:
                        lon = float(longitude) if longitude else None
                    except (ValueError, TypeError):
                        lon = None
                        
                    try:
                        da = float(drainage_area) if drainage_area else None
                    except (ValueError, TypeError):
                        da = None
                    
                    # Determine if this is a HUC 17 station (Pacific Northwest)
                    is_huc17 = huc_code and huc_code.startswith('17') if huc_code else False
                    
                    # Determine basin based on HUC code
                    basin = 'Unknown'
                    if huc_code:
                        huc_prefix = huc_code[:2]
                        basin_map = {
                            '17': 'Pacific Northwest',
                            '16': 'Great Basin',  
                            '18': 'California',
                            '10': 'Missouri',
                            '11': 'Arkansas-White-Red',
                            '12': 'Texas-Gulf',
                            '13': 'Rio Grande',
                            '14': 'Upper Colorado',
                            '15': 'Lower Colorado',
                            '08': 'Lower Mississippi',
                            '07': 'Upper Mississippi',
                            '06': 'Tennessee',
                            '05': 'Ohio',
                            '04': 'Great Lakes',
                            '03': 'South Atlantic-Gulf',
                            '02': 'Mid Atlantic',
                            '01': 'New England'
                        }
                        basin = basin_map.get(huc_prefix, f'HUC {huc_prefix}')
                    
                    site_data = {
                        'site_no': site_code,
                        'station_nm': station_name,
                        'latitude': lat,
                        'longitude': lon,
                        'state_cd': state,
                        'county_cd': site_info.get('county_cd', ''),
                        'huc_cd': huc_code,
                        'huc_code': huc_code[:2] if huc_code else None,  # 2-digit HUC
                        'huc_region': huc_code[:4] if huc_code else None,  # 4-digit HUC
                        'drainage_area': da,
                        'site_type': site_info.get('site_tp_cd', 'ST'),
                        'active': 'Yes',  # Assume active for now - would need separate query for status
                        'basin': basin,
                        'is_huc17': is_huc17,
                        'has_discharge': True  # All have discharge since we queried for it
                    }
                    
                    state_stations.append(site_data)
                    
                except Exception as e:
                    print(f"   ⚠️  Error processing site in {state}: {e}")
                    continue
            
            print(f"   ✅ {state}: {len(state_stations)} stations processed")
            
            # Add HUC 17 summary for this state
            huc17_count = sum(1 for s in state_stations if s.get('is_huc17', False))
            if huc17_count > 0:
                print(f"      📍 HUC 17 stations in {state}: {huc17_count}")
            
            all_stations.extend(state_stations)
            
            # Small delay between states to be respectful to USGS API
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ API request failed for {state}: {e}")
            continue
        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse JSON response for {state}: {e}")
            continue
        except Exception as e:
            print(f"   ❌ Unexpected error for {state}: {e}")
            continue
    
    if not all_stations:
        print("❌ No stations retrieved from any state")
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(all_stations)
    
    # Remove duplicates (same site might appear in multiple queries)
    original_count = len(df)
    df = df.drop_duplicates(subset=['site_no']).reset_index(drop=True)
    
    print(f"\n🎯 SUMMARY:")
    print(f"   Total stations found: {len(df)} (removed {original_count - len(df)} duplicates)")
    print(f"   Active stations: {len(df[df['active'] == 'Yes'])}")
    print(f"   Inactive stations: {len(df[df['active'] == 'No'])}")
    
    # HUC 17 breakdown
    huc17_stations = df[df['is_huc17'] == True]
    print(f"   HUC 17 stations: {len(huc17_stations)} (Pacific Northwest proper)")
    print(f"   Other HUC stations: {len(df) - len(huc17_stations)}")
    
    # State distribution
    print(f"\n📍 State distribution:")
    for state, count in df['state_cd'].value_counts().items():
        huc17_in_state = len(df[(df['state_cd'] == state) & (df['is_huc17'] == True)])
        print(f"   {state}: {count} total ({huc17_in_state} HUC 17)")
    
    # Basin distribution
    print(f"\n🌊 Basin distribution:")
    for basin, count in df['basin'].value_counts().head(10).items():
        print(f"   {basin}: {count} stations")
    
    return df


def save_station_files(df):
    """
    Save station data to multiple files for different use cases.
    
    Args:
        df (pd.DataFrame): Complete stations DataFrame
        
    Returns:
        dict: Dictionary with file paths and counts saved
    """
    if df.empty:
        print("❌ No data to save")
        return {}
    
    results = {}
    
    try:
        # 1. Save all stations (complete dataset)
        all_stations_file = 'all_pnw_discharge_stations.csv'
        df.to_csv(all_stations_file, index=False)
        results['all_stations'] = {'file': all_stations_file, 'count': len(df)}
        print(f"💾 Saved all {len(df)} stations to {all_stations_file}")
        
        # 2. Save HUC 17 stations only (default dashboard view)
        huc17_stations = df[df['is_huc17'] == True].copy()
        if not huc17_stations.empty:
            huc17_file = 'huc17_discharge_stations.csv'
            huc17_stations.to_csv(huc17_file, index=False)
            results['huc17_stations'] = {'file': huc17_file, 'count': len(huc17_stations)}
            print(f"💾 Saved {len(huc17_stations)} HUC 17 stations to {huc17_file}")
        
        # 3. Save active stations only
        active_stations = df[df['active'] == 'Yes'].copy()
        if not active_stations.empty:
            active_file = 'active_pnw_discharge_stations.csv'
            active_stations.to_csv(active_file, index=False)
            results['active_stations'] = {'file': active_file, 'count': len(active_stations)}
            print(f"💾 Saved {len(active_stations)} active stations to {active_file}")
        
        # 4. Save summary statistics
        summary_file = 'stations_summary.txt'
        with open(summary_file, 'w') as f:
            f.write("USGS Pacific Northwest Discharge Stations Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"Total Stations: {len(df)}\n")
            f.write(f"Active Stations: {len(df[df['active'] == 'Yes'])}\n")
            f.write(f"Inactive Stations: {len(df[df['active'] == 'No'])}\n")
            f.write(f"HUC 17 Stations: {len(huc17_stations)}\n\n")
            
            f.write("State Distribution:\n")
            for state, count in df['state_cd'].value_counts().items():
                huc17_count = len(df[(df['state_cd'] == state) & (df['is_huc17'] == True)])
                f.write(f"  {state}: {count} total ({huc17_count} HUC 17)\n")
            
            f.write("\nBasin Distribution:\n")
            for basin, count in df['basin'].value_counts().items():
                f.write(f"  {basin}: {count} stations\n")
            
            f.write("\nFiles Created:\n")
            for key, info in results.items():
                f.write(f"  {info['file']}: {info['count']} stations\n")
        
        results['summary'] = {'file': summary_file, 'count': len(df)}
        print(f"📄 Saved summary to {summary_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error saving files: {e}")
        return {}


def main():
    """Main function to fetch and save Pacific Northwest discharge stations."""
    print("🌊 Pacific Northwest Discharge Stations Fetcher")
    print("=" * 60)
    print("Purpose: Create efficient station list for streamflow dashboard")
    print("Eliminates need to ping 2800+ sites individually")
    print("")
    
    # Fetch the data
    print("Step 1: Fetching stations from USGS API...")
    stations_df = get_state_discharge_stations()
    
    if not stations_df.empty:
        print("\nStep 2: Saving station data files...")
        file_results = save_station_files(stations_df)
        
        if file_results:
            print("\n🎉 SUCCESS! Created efficient station lists:")
            print("\nFor Dashboard Integration:")
            print("  1. Use 'huc17_discharge_stations.csv' for default view (HUC 17 only)")
            print("  2. Use 'all_pnw_discharge_stations.csv' for 'All Stations' toggle")
            print("  3. Filter by 'active' column to show only active stations")
            
            print("\nNext Steps:")
            print("  1. Update dashboard to load from these CSV files instead of API calls")
            print("  2. Add toggle: 'HUC 17 Only' vs 'All PNW Stations'")
            print("  3. Add active/inactive filter option")
            
            # Show sample of HUC 17 data
            huc17_sample = stations_df[stations_df['is_huc17'] == True].head(5)
            if not huc17_sample.empty:
                print(f"\n📋 Sample HUC 17 stations:")
                print(huc17_sample[['site_no', 'station_nm', 'state_cd', 'huc_cd', 'active']].to_string(index=False))
        
    else:
        print("❌ No stations retrieved. Check your internet connection and try again.")


if __name__ == "__main__":
    main()