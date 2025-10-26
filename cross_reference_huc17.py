#!/usr/bin/env python3
"""
Cross-reference HADS discharge stations with existing HUC17 stations.

This script takes the refined HADS station list and matches it with the existing
HUC17 stations file to create a clean Columbia River Basin discharge station list.
"""

import pandas as pd
from typing import Set

def create_huc17_hads_stations():
    """Create HUC17 station list by cross-referencing HADS with existing HUC17 data."""
    
    print("🏔️  Columbia River Basin (HUC17) Station Refinement")
    print("=" * 60)
    print("Cross-referencing NOAA HADS stations with existing HUC17 data")
    print()
    
    # Load the HADS station data (our refined discharge stations)
    print("📂 Loading HADS discharge stations...")
    hads_df = pd.read_csv('pnw_usgs_discharge_stations_hads.csv')
    print(f"📊 HADS stations: {len(hads_df)}")
    
    # Load the existing HUC17 stations
    print("📂 Loading existing HUC17 stations...")
    huc17_df = pd.read_csv('huc17_discharge_stations.csv')
    print(f"📊 Existing HUC17 stations: {len(huc17_df)}")
    
    # Convert site_no columns to strings for matching
    hads_df['usgs_id'] = hads_df['usgs_id'].astype(str)
    huc17_df['site_no'] = huc17_df['site_no'].astype(str)
    
    # Find stations that are in both lists (intersection)
    hads_site_ids = set(hads_df['usgs_id'])
    huc17_site_ids = set(huc17_df['site_no'])
    
    common_sites = hads_site_ids.intersection(huc17_site_ids)
    print(f"🎯 Stations in both HADS and HUC17: {len(common_sites)}")
    
    # Filter HADS data to only HUC17 stations
    huc17_hads_df = hads_df[hads_df['usgs_id'].isin(common_sites)].copy()
    
    # Merge with HUC17 data to get HUC codes and other metadata
    huc17_hads_merged = huc17_hads_df.merge(
        huc17_df[['site_no', 'huc_cd', 'drainage_area', 'huc_code', 'huc_region']],
        left_on='usgs_id',
        right_on='site_no',
        how='left'
    )
    
    # Clean up the merged data
    huc17_hads_merged = huc17_hads_merged.drop('site_no', axis=1)
    
    # Reorder columns for clarity
    column_order = [
        'usgs_id', 'state_code', 'huc_cd', 'huc_code', 'huc_region',
        'nws_id', 'goes_id', 'nws_hsa',
        'latitude_decimal', 'longitude_decimal', 'drainage_area',
        'station_name', 'latitude_dms', 'longitude_dms', 'data_source'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in column_order if col in huc17_hads_merged.columns]
    huc17_final = huc17_hads_merged[available_columns].copy()
    
    # Sort by HUC code, then by USGS ID
    huc17_final = huc17_final.sort_values(['huc_cd', 'usgs_id']).reset_index(drop=True)
    
    # Summary statistics
    print(f"\n📊 Columbia River Basin (HUC17) Summary:")
    print("-" * 45)
    print(f"Total stations: {len(huc17_final)}")
    
    if len(huc17_final) > 0:
        # By state
        print(f"\nStations by state:")
        state_counts = huc17_final['state_code'].value_counts().sort_index()
        for state, count in state_counts.items():
            print(f"   {state}: {count:3d} stations")
        
        # By HUC subregion
        print(f"\nStations by HUC subregion:")
        if 'huc_cd' in huc17_final.columns:
            # Convert HUC codes to strings and handle missing values
            huc_codes = huc17_final['huc_cd'].astype(str).str[:6]
            huc_codes = huc_codes[huc_codes != 'nan']  # Remove NaN values
            if len(huc_codes) > 0:
                huc_counts = huc_codes.value_counts().sort_index()
                for huc, count in huc_counts.head(10).items():
                    huc_name = get_huc_name(huc)
                    print(f"   {huc}: {count:3d} stations ({huc_name})")
    
    # Save the results
    output_file = 'columbia_basin_hads_stations.csv'
    huc17_final.to_csv(output_file, index=False)
    print(f"\n💾 Saved Columbia Basin HADS stations to {output_file}")
    
    # Show sample records
    if len(huc17_final) > 0:
        print(f"\n📋 Sample Columbia Basin HADS stations:")
        print("=" * 80)
        for i in range(min(5, len(huc17_final))):
            row = huc17_final.iloc[i]
            print(f"{row['usgs_id']} ({row['state_code']}) HUC:{row.get('huc_cd', 'N/A')} - {row['station_name'][:45]}...")
            print(f"   NWS: {row['nws_id']}, GOES: {row['goes_id']}")
            if 'drainage_area' in row and pd.notna(row['drainage_area']):
                print(f"   Drainage area: {row['drainage_area']} sq mi")
            print()
    
    # Show what we might be missing
    hads_only = hads_site_ids - huc17_site_ids
    huc17_only = huc17_site_ids - hads_site_ids
    
    print(f"\n🔍 Analysis:")
    print(f"   HADS stations not in HUC17: {len(hads_only)} (outside Columbia Basin)")
    print(f"   HUC17 stations not in HADS: {len(huc17_only)} (not reporting to NWS)")
    
    if len(hads_only) > 0:
        print(f"\n📄 Sample HADS stations outside Columbia Basin:")
        sample_outside = hads_df[hads_df['usgs_id'].isin(list(hads_only))].head(3)
        for _, row in sample_outside.iterrows():
            print(f"   {row['usgs_id']} ({row['state_code']}) - {row['station_name'][:50]}...")
    
    return huc17_final

def get_huc_name(huc_code: str) -> str:
    """Get descriptive name for HUC code."""
    huc_names = {
        '170101': 'Kootenai River',
        '170102': 'Upper Clark Fork',
        '170103': 'Lower Clark Fork',
        '170200': 'Pend Oreille',
        '170300': 'Spokane',
        '170400': 'Upper Columbia',
        '170500': 'Yakima',
        '170600': 'Upper Snake',
        '170700': 'Middle Snake',
        '170701': 'Salmon River',
        '170702': 'Clearwater River',
        '170800': 'Lower Snake',
        '170900': 'Middle Columbia',
        '171000': 'John Day',
        '171001': 'Deschutes River',
        '171100': 'Lower Columbia',
        '171200': 'Oregon Closed Basins'
    }
    return huc_names.get(huc_code[:6], 'Unknown Subbasin')

if __name__ == "__main__":
    huc17_stations = create_huc17_hads_stations()