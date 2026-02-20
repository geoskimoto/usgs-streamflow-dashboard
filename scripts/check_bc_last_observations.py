#!/usr/bin/env python3
"""
Check last observation dates for a random sample of BC stations.
Saves results to CSV for analysis.
"""

import requests
import pandas as pd
import random
from datetime import datetime

# Get all BC stations
base_url = "https://streamflowops.3rdplaces.io"
print("Fetching BC stations...")

stations_response = requests.get(
    f"{base_url}/api/v1/stations/",
    params={'agency': 'EC', 'state': 'BC', 'limit': 10000},
    timeout=30
)

if stations_response.status_code != 200:
    print(f"Error fetching stations: {stations_response.status_code}")
    exit(1)

all_bc_stations = stations_response.json()['results']
station_numbers = [s['station_number'] for s in all_bc_stations]
print(f"Total BC stations: {len(station_numbers)}")

# Sample 500 random stations (or all if less than 500)
sample_size = min(500, len(station_numbers))
sampled_stations = random.sample(station_numbers, sample_size)
print(f"Sampling {sample_size} stations...")

results = []

for i, station_num in enumerate(sampled_stations, 1):
    if i % 50 == 0:
        print(f"  Processed {i}/{sample_size}...")
    
    try:
        # Get the most recent discharge observation for this station
        obs_response = requests.get(
            f"{base_url}/api/v1/observations/discharge/",
            params={
                'station_number': station_num,
                'ordering': '-date',  # Most recent first
                'limit': 1
            },
            timeout=10
        )
        
        if obs_response.status_code == 200:
            obs_data = obs_response.json()
            total_count = obs_data.get('count', 0)
            obs_results = obs_data.get('results', [])
            
            if obs_results:
                latest = obs_results[0]
                results.append({
                    'station_number': station_num,
                    'total_observations': total_count,
                    'last_date': latest.get('date'),
                    'last_value': latest.get('discharge_value'),
                    'unit': latest.get('unit', 'N/A')
                })
            else:
                results.append({
                    'station_number': station_num,
                    'total_observations': 0,
                    'last_date': None,
                    'last_value': None,
                    'unit': None
                })
        else:
            results.append({
                'station_number': station_num,
                'total_observations': 'ERROR',
                'last_date': None,
                'last_value': None,
                'unit': None
            })
    except Exception as e:
        results.append({
            'station_number': station_num,
            'total_observations': f'ERROR: {str(e)}',
            'last_date': None,
            'last_value': None,
            'unit': None
        })

# Convert to DataFrame and save
df = pd.DataFrame(results)
output_file = 'data/bc_stations_last_observation.csv'
df.to_csv(output_file, index=False)

print(f"\n✓ Saved results to: {output_file}")
print(f"\nSummary:")
print(f"  Total sampled: {len(df)}")
print(f"  With data: {len(df[df['total_observations'] > 0])}")
print(f"  No data: {len(df[df['total_observations'] == 0])}")

# Show date distribution
df_with_dates = df[df['last_date'].notna()].copy()
if not df_with_dates.empty:
    df_with_dates['last_date'] = pd.to_datetime(df_with_dates['last_date'])
    df_with_dates['year'] = df_with_dates['last_date'].dt.year
    
    print(f"\nLast observation year distribution:")
    year_counts = df_with_dates['year'].value_counts().sort_index(ascending=False)
    for year, count in year_counts.head(10).items():
        print(f"  {year}: {count} stations")
    
    if not df_with_dates.empty:
        print(f"\nMost recent data: {df_with_dates['last_date'].max()}")
        print(f"Oldest data in sample: {df_with_dates['last_date'].min()}")
        
        # Check how many have data in last 6 months
        recent_threshold = pd.Timestamp.now() - pd.Timedelta(days=180)
        recent_count = len(df_with_dates[df_with_dates['last_date'] >= recent_threshold])
        print(f"\nStations with data in last 6 months: {recent_count} ({recent_count/len(df)*100:.1f}%)")
