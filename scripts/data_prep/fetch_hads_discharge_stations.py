#!/usr/bin/env python3
"""
Fetch USGS discharge stations from NOAA HADS for Pacific Northwest states.

This script fetches USGS station data from NOAA's Hydrometeorological Automated Data System (HADS)
for OR, WA, ID, MT, NV, and CA. These are actual discharge monitoring stations, not all USGS sites.

HADS provides USGS sites that report to the National Weather Service, which are typically
the most important discharge monitoring stations for flood forecasting and water management.
"""

import requests
import pandas as pd
import time
from typing import List, Dict
import os

class HADSDataFetcher:
    """Fetch USGS discharge station data from NOAA HADS."""
    
    def __init__(self):
        self.base_url = "https://hads.ncep.noaa.gov/USGS/{}_USGS-HADS_SITES.txt"
        self.states = ['WA', 'OR', 'ID', 'MT', 'NV', 'CA']
        self.session = requests.Session()
        
    def fetch_state_data(self, state_code: str) -> pd.DataFrame:
        """
        Fetch HADS data for a specific state.
        
        Parameters:
        -----------
        state_code : str
            Two-letter state code (e.g., 'WA', 'OR')
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with station information
        """
        url = self.base_url.format(state_code)
        print(f"📡 Fetching {state_code} stations from: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse the fixed-width format
            lines = response.text.strip().split('\n')
            
            # Find the separator line (dashes) to identify where data starts
            data_start_idx = None
            for i, line in enumerate(lines):
                if line.startswith('-----'):
                    data_start_idx = i + 1
                    break
            
            if data_start_idx is None:
                print(f"⚠️  Could not find data separator in {state_code} data")
                return pd.DataFrame()
            
            # Extract data lines (skip headers and separator)
            data_lines = lines[data_start_idx:]
            
            # Parse fixed-width format
            stations = []
            skipped_lines = 0
            
            for line in data_lines:
                if len(line.strip()) == 0 or line.startswith('#'):
                    continue
                    
                # Parse the fixed-width columns based on the format
                station = self._parse_hads_line(line, state_code)
                if station:
                    stations.append(station)
                else:
                    skipped_lines += 1
                    # Debug first few skipped lines
                    if skipped_lines <= 3:
                        usgs_part = line[6:21].strip() if len(line) > 21 else "N/A"
                        print(f"   Debug skip: USGS_ID='{usgs_part}' in line: {line[:50]}...")
            
            df = pd.DataFrame(stations)
            print(f"✅ {state_code}: Found {len(df)} stations (skipped {skipped_lines} lines)")
            
            # Debug: show first few successful parses
            if len(df) > 0:
                print(f"   Sample: {df.iloc[0]['usgs_id']} - {df.iloc[0]['station_name'][:30]}...")
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching {state_code} data: {e}")
            return pd.DataFrame()
    
    def _parse_hads_line(self, line: str, state_code: str) -> Dict:
        """Parse a single line of HADS data using fixed-width format."""
        try:
            # Skip lines that are too short or are separators
            if len(line) < 50 or line.startswith('---'):
                return None
            
            # HADS format (based on actual data analysis):
            # Columns: NWS_ID | USGS_ID | GOES_ID | NWS | LAT | LON | NAME
            # Positions: 0-5 | 6-21 | 22-30 | 31-34 | 35-46 | 47-59 | 60+
            # Separators at positions: 5, 21, 30, 34, 46, 59
            
            if len(line) < 50:
                return None
                
            nws_id = line[0:5].strip()
            usgs_id = line[6:21].strip() 
            goes_id = line[22:30].strip()
            nws_hsa = line[31:34].strip()
            latitude_str = line[35:46].strip()
            longitude_str = line[47:59].strip() if len(line) > 59 else ""
            station_name = line[60:].strip() if len(line) > 60 else ""
            
            # Skip if no USGS ID (allow for 8+ digit numbers)
            if not usgs_id or not usgs_id.replace('.', '').isdigit() or len(usgs_id) < 8:
                return None
            
            # Parse coordinates from "dd mm ss" format to decimal degrees
            def dms_to_decimal(dms_str: str, is_longitude: bool = False) -> float:
                """Convert 'dd mm ss' to decimal degrees."""
                try:
                    parts = dms_str.split()
                    if len(parts) == 3:
                        dd, mm, ss = map(float, parts)
                        decimal = dd + mm/60 + ss/3600
                        # Longitude is negative in western US
                        if is_longitude and decimal > 0:
                            decimal = -decimal
                        return decimal
                except:
                    pass
                return None
            
            lat_decimal = dms_to_decimal(latitude_str)
            lon_decimal = dms_to_decimal(longitude_str, is_longitude=True)
            
            station = {
                'state_code': state_code,
                'nws_id': nws_id,
                'usgs_id': usgs_id,
                'goes_id': goes_id if goes_id else None,
                'nws_hsa': nws_hsa if nws_hsa else None,
                'latitude_dms': latitude_str,
                'longitude_dms': longitude_str,
                'latitude_decimal': lat_decimal,
                'longitude_decimal': lon_decimal,
                'station_name': station_name,
                'raw_line': line.strip()
            }
            
            return station
            
        except Exception as e:
            print(f"Error parsing line: {line[:50]}... - {e}")
            return None
    
    def _is_coordinate(self, text: str) -> bool:
        """Check if text looks like a coordinate."""
        try:
            val = float(text)
            # Rough bounds for North America
            return (-180 <= val <= 180) and (abs(val) > 1)
        except:
            return False
    
    def fetch_all_states(self) -> pd.DataFrame:
        """Fetch data for all Pacific Northwest states."""
        all_stations = []
        
        for state in self.states:
            print(f"\n🗺️  Processing {state}...")
            df = self.fetch_state_data(state)
            if not df.empty:
                all_stations.append(df)
            
            # Be nice to the server
            time.sleep(1)
        
        if all_stations:
            combined_df = pd.concat(all_stations, ignore_index=True)
            print(f"\n🎯 Total stations found: {len(combined_df)}")
            return combined_df
        else:
            print("❌ No data retrieved from any state")
            return pd.DataFrame()
    
    def save_to_csv(self, df: pd.DataFrame, filename: str = "usgs_hads_discharge_stations.csv"):
        """Save the combined data to CSV."""
        if df.empty:
            print("❌ No data to save")
            return
        
        # Clean up the data before saving
        df_clean = df.copy()
        
        # Remove duplicates based on USGS ID
        if 'usgs_id' in df_clean.columns:
            initial_count = len(df_clean)
            df_clean = df_clean.drop_duplicates(subset=['usgs_id'])
            final_count = len(df_clean)
            if initial_count != final_count:
                print(f"🔄 Removed {initial_count - final_count} duplicate stations")
        
        # Save to CSV
        df_clean.to_csv(filename, index=False)
        print(f"💾 Saved {len(df_clean)} stations to {filename}")
        
        # Show summary
        print(f"\n📊 Summary by state:")
        if 'state_code' in df_clean.columns:
            state_counts = df_clean['state_code'].value_counts()
            for state, count in state_counts.items():
                print(f"   {state}: {count} stations")

def main():
    """Main function to fetch and process HADS data."""
    print("🚀 Fetching USGS Discharge Stations from NOAA HADS")
    print("=" * 60)
    print("States: OR, WA, ID, MT, NV, CA")
    print("Source: NOAA Hydrometeorological Automated Data System")
    print()
    
    fetcher = HADSDataFetcher()
    
    # Fetch data for all states
    df = fetcher.fetch_all_states()
    
    if not df.empty:
        # Save the raw data
        fetcher.save_to_csv(df, "usgs_hads_raw_data.csv")
        
        # We'll need to do more detailed parsing of the fixed-width format
        # Let's first see what the data looks like
        print(f"\n🔍 Sample of raw data:")
        print("=" * 40)
        if 'raw_line' in df.columns:
            for i, line in enumerate(df['raw_line'].head(5)):
                print(f"{i+1}. {line}")
        
        print(f"\n💡 Next steps:")
        print("1. Examine the raw data format")
        print("2. Create a proper parser for the fixed-width format")
        print("3. Extract all relevant fields (USGS_ID, GOES_ID, NWS_ID, coordinates, name)")
        print("4. Create a clean CSV with standardized columns")
    else:
        print("❌ Failed to retrieve any data")

if __name__ == "__main__":
    main()