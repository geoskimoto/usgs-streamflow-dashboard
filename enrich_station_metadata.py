#!/usr/bin/env python3
"""
Enrich station metadata in the filters table with calculated statistics.

This script queries the collected discharge data (realtime and daily) to calculate:
- Number of water years with data
- Last data date
- Data availability status
- Years of record
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path


def calculate_station_statistics(cache_db_path: str, logger=None, quiet: bool = False):
    """
    Calculate statistics from collected data and update filters table.
    
    Parameters:
    -----------
    cache_db_path : str
        Path to the cache database
    logger : logging.Logger, optional
        Logger instance to use for output. If None, uses print()
    quiet : bool
        If True, suppress progress messages (only final count)
    """
    
    def log(message):
        """Helper to log or print depending on configuration."""
        if logger:
            logger.info(message)
        elif not quiet:
            print(message)
    
    if not quiet:
        log("🔍 Analyzing collected discharge data...")
    
    conn = sqlite3.connect(cache_db_path)
    
    # Get list of stations in filters
    filters_df = pd.read_sql("SELECT site_id FROM filters", conn)
    if not quiet:
        log(f"📊 Found {len(filters_df)} stations in filters table")
    
    updated_count = 0
    
    for idx, row in filters_df.iterrows():
        site_id = row['site_id']
        
        # Calculate statistics from both realtime and daily data
        stats = calculate_site_stats(conn, site_id)
        
        if stats:
            # Update filters table with calculated stats
            conn.execute("""
                UPDATE filters SET
                    num_water_years = ?,
                    years_of_record = ?,
                    last_data_date = ?,
                    is_active = ?,
                    last_updated = ?
                WHERE site_id = ?
            """, (
                stats['num_water_years'],
                stats['years_of_record'],
                stats['last_data_date'],
                stats['is_active'],
                datetime.now().isoformat(),
                site_id
            ))
            updated_count += 1
            
            if not quiet and (idx + 1) % 100 == 0:
                log(f"  Progress: {idx + 1}/{len(filters_df)} stations processed")
    
    conn.commit()
    conn.close()
    
    if not quiet:
        log(f"\n✅ Updated statistics for {updated_count} stations")
    return updated_count


def calculate_site_stats(conn, site_id):
    """Calculate statistics for a single site from available data."""
    
    stats = {
        'num_water_years': 0,
        'years_of_record': 0,
        'last_data_date': None,
        'is_active': 0
    }
    
    # Try streamflow_data FIRST (has full historical data from 1910-present as JSON)
    try:
        streamflow_query = """
            SELECT data_json, start_date, end_date 
            FROM streamflow_data 
            WHERE site_id = ?
            ORDER BY end_date DESC
            LIMIT 1
        """
        cursor = conn.cursor()
        cursor.execute(streamflow_query, (site_id,))
        result = cursor.fetchone()
        
        if result:
            data_json, start_date, end_date = result
            
            # Parse the JSON data to get years
            import json
            data = json.loads(data_json)
            
            if data:
                # Extract years from the datetime field in each record
                years = set()
                for record in data:
                    date_str = record.get('datetime', '')
                    if date_str:
                        year = int(date_str.split('-')[0])
                        years.add(year)
                
                stats['num_water_years'] = len(years)
                stats['last_data_date'] = end_date
                
                # Years of record (span from first to last year)
                if years:
                    stats['years_of_record'] = max(years) - min(years) + 1
                
                # Check if active (data within last 60 days)
                from datetime import datetime
                last_date = datetime.strptime(end_date, '%Y-%m-%d')
                days_since_last = (datetime.now() - last_date).days
                stats['is_active'] = 1 if days_since_last <= 60 else 0
                
                return stats
    except Exception as e:
        # print(f"Warning: Error checking streamflow_data for {site_id}: {e}")
        pass
    
    # Fall back to realtime_discharge if streamflow_data doesn't exist
    try:
        realtime_query = """
            SELECT datetime_utc 
            FROM realtime_discharge 
            WHERE site_no = ?
            ORDER BY datetime_utc DESC
        """
        realtime_df = pd.read_sql(realtime_query, conn, params=(site_id,))
        
        if not realtime_df.empty:
            realtime_df['datetime_utc'] = pd.to_datetime(realtime_df['datetime_utc'])
            
            # Get last data date
            last_date = realtime_df['datetime_utc'].max()
            stats['last_data_date'] = last_date.strftime('%Y-%m-%d')
            
            # Check if active (data within last 60 days)
            days_since_last = (datetime.now() - last_date).days
            stats['is_active'] = 1 if days_since_last <= 60 else 0
            
            # Calculate water years (unique years)
            water_years = realtime_df['datetime_utc'].dt.year.unique()
            stats['num_water_years'] = len(water_years)
            
            # Years of record
            if len(water_years) > 0:
                stats['years_of_record'] = water_years.max() - water_years.min() + 1
            
            return stats
    except Exception as e:
        # print(f"Warning: Error checking daily data for {site_id}: {e}")
        pass
    
    # If no data found, return None to skip update
    return None


def enrich_from_usgs_api(cache_db_path: str, sample_size: int = None):
    """
    Fetch additional metadata from USGS API for stations that need it.
    This includes drainage_area, county, huc_code, etc.
    
    Parameters:
    -----------
    cache_db_path : str
        Path to the cache database
    sample_size : int, optional
        Number of stations to update (for testing). None = all stations.
    """
    
    print("\n🌐 Fetching additional metadata from USGS API...")
    print("   (This may take a while for many stations)")
    
    try:
        import dataretrieval.nwis as nwis
    except ImportError:
        print("❌ dataretrieval package not available. Skipping USGS API enrichment.")
        return 0
    
    conn = sqlite3.connect(cache_db_path)
    
    # Get stations that are missing drainage_area or county
    query = """
        SELECT site_id 
        FROM filters 
        WHERE drainage_area IS NULL OR county IS NULL
        ORDER BY site_id
    """
    
    if sample_size:
        query += f" LIMIT {sample_size}"
    
    stations_df = pd.read_sql(query, conn)
    print(f"📊 Found {len(stations_df)} stations needing metadata enrichment")
    
    if len(stations_df) == 0:
        conn.close()
        return 0
    
    updated_count = 0
    
    for idx, row in stations_df.iterrows():
        site_id = row['site_id']
        
        try:
            # Fetch site info from USGS
            site_info = nwis.get_record(sites=site_id, service='site')
            
            if site_info is not None and not site_info.empty:
                site = site_info.iloc[0]
                
                # Extract metadata
                drainage_area = site.get('drain_area_va', None)
                county = site.get('county_nm', None)
                huc_code = site.get('huc_cd', None)
                site_type = site.get('site_tp_cd', None)
                
                # Update filters table
                conn.execute("""
                    UPDATE filters SET
                        drainage_area = ?,
                        county = ?,
                        huc_code = ?,
                        site_type = ?,
                        last_updated = ?
                    WHERE site_id = ?
                """, (
                    drainage_area,
                    county,
                    huc_code,
                    site_type or 'Stream',
                    datetime.now().isoformat(),
                    site_id
                ))
                
                updated_count += 1
                
                if (idx + 1) % 25 == 0:
                    print(f"  Progress: {idx + 1}/{len(stations_df)} stations enriched")
                    conn.commit()  # Commit periodically
                    
        except Exception as e:
            print(f"  ⚠️  Could not fetch metadata for {site_id}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Enriched {updated_count} stations with USGS API data")
    return updated_count


def main():
    """Main execution function."""
    
    cache_db = Path('data/usgs_cache.db')
    
    if not cache_db.exists():
        print(f"❌ Cache database not found: {cache_db}")
        return False
    
    print("=" * 60)
    print("STATION METADATA ENRICHMENT")
    print("=" * 60)
    
    # Step 1: Calculate statistics from collected data
    print("\n📊 STEP 1: Calculating statistics from collected data")
    print("-" * 60)
    stats_updated = calculate_station_statistics(str(cache_db))
    
    # Step 2: Fetch additional metadata from USGS API (optional)
    print("\n" + "=" * 60)
    response = input("Fetch additional metadata from USGS API? (y/N): ")
    
    if response.lower() == 'y':
        print("\n🌐 STEP 2: Fetching metadata from USGS API")
        print("-" * 60)
        
        # Ask if they want to test with a sample first
        sample_response = input("Test with sample size first? Enter number (e.g., 50) or press Enter for all: ")
        
        sample_size = None
        if sample_response.strip():
            try:
                sample_size = int(sample_response.strip())
            except ValueError:
                print("Invalid number, processing all stations...")
        
        api_updated = enrich_from_usgs_api(str(cache_db), sample_size)
        
        print(f"\n✅ Total enrichment complete!")
        print(f"   Statistics updated: {stats_updated} stations")
        print(f"   API metadata enriched: {api_updated} stations")
    else:
        print("\n✅ Statistics enrichment complete!")
        print(f"   Updated: {stats_updated} stations")
    
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
