#!/usr/bin/env python3
"""
Clean and format the HADS discharge station data into a standardized CSV.
"""

import pandas as pd
import re

def clean_hads_data():
    """Clean and standardize the HADS data."""
    
    # Read the raw data
    df = pd.read_csv('usgs_hads_raw_data.csv')
    
    print(f"📊 Processing {len(df)} raw HADS records...")
    
    # Create clean dataframe with standardized columns
    clean_data = []
    
    for idx, row in df.iterrows():
        try:
            # Parse coordinates from DMS to decimal
            def dms_to_decimal(dms_str: str, is_longitude: bool = False) -> float:
                """Convert 'dd mm ss' to decimal degrees."""
                try:
                    if pd.isna(dms_str) or not dms_str:
                        return None
                    parts = str(dms_str).split()
                    if len(parts) >= 3:
                        dd = float(parts[0])
                        mm = float(parts[1]) 
                        ss = float(parts[2])
                        decimal = dd + mm/60 + ss/3600
                        # Western longitude is negative
                        if is_longitude and decimal > 0:
                            decimal = -decimal
                        return round(decimal, 6)
                except:
                    pass
                return None
            
            # Extract clean station name (handle line wrapping)
            station_name = str(row.get('station_name', '')).strip()
            
            # Remove common abbreviations and clean up
            station_name = re.sub(r'\s+', ' ', station_name)  # Multiple spaces to single
            station_name = station_name.replace(' WA', ' WA').replace(' OR', ' OR').replace(' ID', ' ID')  # Ensure proper state formatting
            
            clean_record = {
                'usgs_id': str(row['usgs_id']).strip(),
                'nws_id': str(row.get('nws_id', '')).strip(),
                'goes_id': str(row.get('goes_id', '')).strip(),
                'nws_hsa': str(row.get('nws_hsa', '')).strip(),
                'state_code': row['state_code'],
                'latitude_decimal': dms_to_decimal(row.get('latitude_dms')),
                'longitude_decimal': dms_to_decimal(row.get('longitude_dms'), is_longitude=True),
                'latitude_dms': str(row.get('latitude_dms', '')).strip(),
                'longitude_dms': str(row.get('longitude_dms', '')).strip(),
                'station_name': station_name,
                'data_source': 'NOAA_HADS'
            }
            
            # Only include records with valid USGS ID and coordinates
            if (clean_record['usgs_id'] and 
                clean_record['latitude_decimal'] is not None and 
                clean_record['longitude_decimal'] is not None):
                clean_data.append(clean_record)
                
        except Exception as e:
            print(f"Error processing row {idx}: {e}")
            continue
    
    # Create clean dataframe
    clean_df = pd.DataFrame(clean_data)
    
    # Remove duplicates based on USGS ID (keep first occurrence)
    initial_count = len(clean_df)
    clean_df = clean_df.drop_duplicates(subset=['usgs_id'], keep='first')
    final_count = len(clean_df)
    
    if initial_count != final_count:
        print(f"🔄 Removed {initial_count - final_count} duplicate USGS IDs")
    
    # Sort by state, then by USGS ID
    clean_df = clean_df.sort_values(['state_code', 'usgs_id']).reset_index(drop=True)
    
    # Save the clean data
    output_file = 'pnw_usgs_discharge_stations_hads.csv'
    clean_df.to_csv(output_file, index=False)
    
    print(f"💾 Saved {len(clean_df)} clean discharge stations to {output_file}")
    
    # Summary statistics
    print(f"\n📊 Summary by state:")
    state_counts = clean_df['state_code'].value_counts().sort_index()
    for state, count in state_counts.items():
        print(f"   {state}: {count:3d} stations")
    
    print(f"\n🎯 Total Pacific Northwest USGS Discharge Stations: {len(clean_df)}")
    
    # Show sample records
    print(f"\n📋 Sample records:")
    print("=" * 80)
    for i in range(min(5, len(clean_df))):
        row = clean_df.iloc[i]
        print(f"{row['usgs_id']} ({row['state_code']}) - {row['station_name'][:50]}...")
        print(f"   Coords: {row['latitude_decimal']:.4f}, {row['longitude_decimal']:.4f}")
        print(f"   NWS: {row['nws_id']}, GOES: {row['goes_id']}")
        print()
    
    return clean_df

if __name__ == "__main__":
    clean_df = clean_hads_data()