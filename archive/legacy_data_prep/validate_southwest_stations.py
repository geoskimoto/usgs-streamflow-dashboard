#!/usr/bin/env python3
"""
Validate which Southwest stations actually have discharge data available.
Tests each station by attempting to fetch recent data from USGS.
"""

import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_station_has_data(site_id, max_retries=2):
    """
    Test if a station has discharge data available from USGS.
    
    Args:
        site_id: USGS site ID
        max_retries: Number of retry attempts
    
    Returns:
        tuple: (has_data: bool, error_msg: str or None)
    """
    # Try recent 1 year of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    url = "https://waterservices.usgs.gov/nwis/dv"
    params = {
        'format': 'json',
        'sites': site_id,
        'parameterCd': '00060',  # Discharge
        'startDT': start_date.strftime('%Y-%m-%d'),
        'endDT': end_date.strftime('%Y-%m-%d')
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if data exists
                if 'value' in data and 'timeSeries' in data['value']:
                    time_series = data['value']['timeSeries']
                    if time_series and len(time_series) > 0:
                        values = time_series[0].get('values', [])
                        if values and len(values) > 0:
                            value_list = values[0].get('value', [])
                            if len(value_list) > 0:
                                return (True, None)
                
                return (False, "No data in response")
            
            elif response.status_code == 400:
                return (False, f"Bad Request - Invalid site or parameters")
            
            elif response.status_code == 404:
                return (False, "Site not found")
            
            else:
                return (False, f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return (False, "Timeout")
        
        except Exception as e:
            return (False, f"Error: {str(e)}")
    
    return (False, "Max retries exceeded")


def validate_stations(csv_file, output_file, sample_size=None):
    """
    Validate stations from CSV file.
    
    Args:
        csv_file: Path to CSV with station data
        output_file: Path to save validated stations
        sample_size: Optional - test only first N stations per state
    """
    print(f"🔍 Validating stations from {csv_file}")
    print("=" * 70)
    
    # Load stations - preserve leading zeros in site_no
    df = pd.read_csv(csv_file, dtype={'site_no': str})
    print(f"\nTotal stations in file: {len(df)}")
    
    # Group by state
    states = df['state_cd'].unique()
    print(f"States: {', '.join(states)}\n")
    
    valid_stations = []
    invalid_stations = []
    
    for state in sorted(states):
        state_df = df[df['state_cd'] == state]
        
        if sample_size:
            state_df = state_df.head(sample_size)
        
        print(f"\n{'='*70}")
        print(f"Testing {state}: {len(state_df)} stations")
        print(f"{'='*70}")
        
        valid_count = 0
        invalid_count = 0
        
        for idx, row in state_df.iterrows():
            site_id = str(row['site_no']).zfill(8)  # Ensure 8 digits with leading zeros
            station_name = row['station_nm']
            
            # Test the station
            has_data, error = test_station_has_data(site_id)
            
            if has_data:
                valid_count += 1
                valid_stations.append(row)
                print(f"  ✅ {site_id}: {station_name[:50]}")
            else:
                invalid_count += 1
                invalid_stations.append({
                    'site_no': site_id,
                    'station_nm': station_name,
                    'state_cd': state,
                    'error': error
                })
                print(f"  ❌ {site_id}: {error}")
            
            # Rate limiting
            time.sleep(0.5)
        
        print(f"\n{state} Summary: {valid_count} valid, {invalid_count} invalid")
    
    # Save results
    print(f"\n{'='*70}")
    print("VALIDATION SUMMARY")
    print(f"{'='*70}")
    
    if valid_stations:
        valid_df = pd.DataFrame(valid_stations)
        valid_df.to_csv(output_file, index=False)
        print(f"\n✅ Valid stations: {len(valid_stations)}")
        print(f"   Saved to: {output_file}")
        
        print("\n   By state:")
        for state in sorted(valid_df['state_cd'].unique()):
            count = len(valid_df[valid_df['state_cd'] == state])
            print(f"      {state}: {count}")
    
    if invalid_stations:
        invalid_df = pd.DataFrame(invalid_stations)
        invalid_file = output_file.replace('.csv', '_invalid.csv')
        invalid_df.to_csv(invalid_file, index=False)
        print(f"\n❌ Invalid stations: {len(invalid_stations)}")
        print(f"   Saved to: {invalid_file}")
        
        print("\n   By state:")
        for state in sorted(invalid_df['state_cd'].unique()):
            count = len(invalid_df[invalid_df['state_cd'] == state])
            print(f"      {state}: {count}")
        
        # Show error breakdown
        print("\n   Error types:")
        error_counts = invalid_df['error'].value_counts()
        for error, count in error_counts.items():
            print(f"      {error}: {count}")
    
    print(f"\n{'='*70}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate USGS station data availability')
    parser.add_argument('--sample', type=int, help='Test only N stations per state')
    parser.add_argument('--full', action='store_true', help='Test all stations (takes a long time!)')
    
    args = parser.parse_args()
    
    csv_file = 'data/southwest_discharge_stations.csv'
    output_file = 'data/southwest_discharge_stations_validated.csv'
    
    # Default to sample of 20 per state unless --full specified
    sample_size = args.sample if args.sample else (None if args.full else 20)
    
    if sample_size:
        print(f"📊 Testing {sample_size} stations per state (sample mode)")
    else:
        print(f"⚠️  Testing ALL stations - this will take a LONG time!")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
    
    validate_stations(csv_file, output_file, sample_size)
