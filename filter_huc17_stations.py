#!/usr/bin/env python3
"""
Filter HADS discharge stations to Columbia River Basin (HUC17) using USGS Web Services.

This script takes our refined HADS discharge station list and queries the USGS Site Web Service
to get HUC codes for each station, then filters to only include HUC17 (Columbia River Basin) stations.
"""

import pandas as pd
import requests
import time
import json
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

class HUC17Filter:
    """Filter discharge stations to Columbia River Basin (HUC17)."""
    
    def __init__(self):
        self.usgs_site_service = "https://waterservices.usgs.gov/nwis/site/"
        self.session = requests.Session()
        self.batch_size = 100  # Process in batches to avoid overwhelming the API
        
    def get_site_info_batch(self, site_ids: List[str]) -> Dict[str, Dict]:
        """
        Get site information including HUC codes for a batch of sites.
        
        Parameters:
        -----------
        site_ids : List[str]
            List of USGS site IDs
            
        Returns:
        --------
        Dict[str, Dict]
            Dictionary mapping site_id to site info including HUC code
        """
        try:
            # Create comma-separated list of site IDs
            sites_param = ','.join(site_ids)
            
            params = {
                'format': 'rdb',
                'sites': sites_param,
                'siteOutput': 'expanded',  # Get expanded site information including HUC
                'siteStatus': 'all'  # Include both active and inactive sites
            }
            
            print(f"🔍 Querying USGS for {len(site_ids)} sites...")
            
            response = self.session.get(self.usgs_site_service, params=params, timeout=60)
            response.raise_for_status()
            
            # Parse RDB format response
            site_info = {}
            lines = response.text.strip().split('\n')
            
            # Find header line (starts with # and contains column names)
            header_line = None
            data_start = 0
            
            for i, line in enumerate(lines):
                if line.startswith('#') and 'site_no' in line.lower():
                    header_line = line[1:].strip()  # Remove leading #
                    # Next line should be data format indicators, skip it
                    data_start = i + 2
                    break
            
            if header_line is None:
                print("⚠️  Could not find header in USGS response")
                return {}
            
            # Parse header
            headers = [h.strip() for h in header_line.split('\t')]
            
            # Find relevant column indices
            try:
                site_no_idx = headers.index('site_no')
                huc_cd_idx = headers.index('huc_cd') if 'huc_cd' in headers else None
                station_nm_idx = headers.index('station_nm') if 'station_nm' in headers else None
                dec_lat_idx = headers.index('dec_lat_va') if 'dec_lat_va' in headers else None
                dec_lon_idx = headers.index('dec_long_va') if 'dec_long_va' in headers else None
                drain_area_idx = headers.index('drain_area_va') if 'drain_area_va' in headers else None
            except ValueError as e:
                print(f"❌ Missing required columns in USGS response: {e}")
                return {}
            
            # Parse data lines
            for line in lines[data_start:]:
                if line.strip() and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) > site_no_idx:
                        site_id = parts[site_no_idx].strip()
                        
                        site_data = {
                            'site_no': site_id,
                            'huc_cd': parts[huc_cd_idx].strip() if huc_cd_idx and len(parts) > huc_cd_idx else None,
                            'station_nm': parts[station_nm_idx].strip() if station_nm_idx and len(parts) > station_nm_idx else None,
                            'dec_lat_va': parts[dec_lat_idx].strip() if dec_lat_idx and len(parts) > dec_lat_idx else None,
                            'dec_long_va': parts[dec_lon_idx].strip() if dec_lon_idx and len(parts) > dec_lon_idx else None,
                            'drain_area_va': parts[drain_area_idx].strip() if drain_area_idx and len(parts) > drain_area_idx else None
                        }
                        
                        site_info[site_id] = site_data
            
            print(f"✅ Retrieved info for {len(site_info)} sites")
            return site_info
            
        except Exception as e:
            print(f"❌ Error querying USGS site service: {e}")
            return {}
    
    def filter_to_huc17(self, input_csv: str = 'pnw_usgs_discharge_stations_hads.csv') -> pd.DataFrame:
        """
        Filter the HADS station list to only HUC17 (Columbia River Basin) stations.
        
        Parameters:
        -----------
        input_csv : str
            Path to input CSV file with HADS stations
            
        Returns:
        --------
        pd.DataFrame
            Filtered dataframe with only HUC17 stations
        """
        # Load the HADS station data
        print(f"📂 Loading station data from {input_csv}...")
        df = pd.read_csv(input_csv)
        print(f"📊 Initial station count: {len(df)}")
        
        # Get unique site IDs and ensure they're strings
        site_ids = [str(site_id) for site_id in df['usgs_id'].unique().tolist()]
        
        # Process in batches
        all_site_info = {}
        
        for i in range(0, len(site_ids), self.batch_size):
            batch = site_ids[i:i + self.batch_size]
            batch_info = self.get_site_info_batch(batch)
            all_site_info.update(batch_info)
            
            # Be nice to the USGS servers
            if i + self.batch_size < len(site_ids):
                print("⏸️  Waiting 2 seconds between batches...")
                time.sleep(2)
        
        # Add HUC codes to the dataframe
        print("🔗 Matching HUC codes to stations...")
        df['huc_cd'] = df['usgs_id'].map(lambda x: all_site_info.get(str(x), {}).get('huc_cd'))
        df['usgs_station_name'] = df['usgs_id'].map(lambda x: all_site_info.get(str(x), {}).get('station_nm'))
        df['drainage_area'] = df['usgs_id'].map(lambda x: all_site_info.get(str(x), {}).get('drain_area_va'))
        
        # Filter to HUC17 (Columbia River Basin)
        print("🏔️  Filtering to Columbia River Basin (HUC17)...")
        
        # HUC17 includes all HUC codes starting with "17"
        huc17_mask = df['huc_cd'].str.startswith('17', na=False)
        df_huc17 = df[huc17_mask].copy()
        
        print(f"✅ Found {len(df_huc17)} stations in Columbia River Basin (HUC17)")
        
        # Show summary by state
        if len(df_huc17) > 0:
            print("\n📊 HUC17 stations by state:")
            state_counts = df_huc17['state_code'].value_counts().sort_index()
            for state, count in state_counts.items():
                print(f"   {state}: {count:3d} stations")
            
            # Show HUC code distribution
            print(f"\n🗺️  HUC code distribution:")
            huc_counts = df_huc17['huc_cd'].str[:6].value_counts().sort_index()  # First 6 digits
            for huc, count in huc_counts.head(10).items():
                print(f"   {huc}*: {count:3d} stations")
        
        return df_huc17
    
    def save_huc17_stations(self, df_huc17: pd.DataFrame, output_file: str = 'columbia_basin_discharge_stations.csv'):
        """Save the HUC17 stations to CSV."""
        if df_huc17.empty:
            print("❌ No HUC17 stations to save")
            return
        
        # Reorder columns for clarity
        column_order = [
            'usgs_id', 'state_code', 'huc_cd', 'nws_id', 'goes_id', 'nws_hsa',
            'latitude_decimal', 'longitude_decimal', 'drainage_area',
            'station_name', 'usgs_station_name', 
            'latitude_dms', 'longitude_dms', 'data_source'
        ]
        
        # Only include columns that exist
        available_columns = [col for col in column_order if col in df_huc17.columns]
        df_output = df_huc17[available_columns].copy()
        
        # Sort by HUC code, then by USGS ID
        df_output = df_output.sort_values(['huc_cd', 'usgs_id']).reset_index(drop=True)
        
        # Save to CSV
        df_output.to_csv(output_file, index=False)
        print(f"💾 Saved {len(df_output)} Columbia Basin stations to {output_file}")
        
        # Show sample records
        print(f"\n📋 Sample Columbia Basin stations:")
        print("=" * 80)
        for i in range(min(5, len(df_output))):
            row = df_output.iloc[i]
            print(f"{row['usgs_id']} ({row['state_code']}) HUC:{row['huc_cd']} - {row['station_name'][:40]}...")
            if 'drainage_area' in row and pd.notna(row['drainage_area']):
                print(f"   Drainage area: {row['drainage_area']} sq mi")
            print()

def main():
    """Main function to filter HADS stations to Columbia River Basin."""
    print("🏔️  Columbia River Basin (HUC17) Station Filter")
    print("=" * 60)
    print("Filtering NOAA HADS discharge stations to Columbia River Basin")
    print()
    
    filter_tool = HUC17Filter()
    
    # Filter to HUC17
    df_huc17 = filter_tool.filter_to_huc17()
    
    if not df_huc17.empty:
        # Save the filtered list
        filter_tool.save_huc17_stations(df_huc17)
        
        print(f"\n🎯 Columbia River Basin Summary:")
        print(f"   Total discharge stations: {len(df_huc17)}")
        print(f"   States covered: {', '.join(sorted(df_huc17['state_code'].unique()))}")
        print(f"   Output file: columbia_basin_discharge_stations.csv")
        
        return df_huc17
    else:
        print("❌ No Columbia River Basin stations found")
        return None

if __name__ == "__main__":
    main()