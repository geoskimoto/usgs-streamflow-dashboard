"""
Configurable USGS Data Collection Framework

This module provides a unified framework for collecting both real-time and daily
USGS discharge data using database-driven station configurations instead of
hardcoded station lists.
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json
import time
import argparse
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Add the project root to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from json_config_manager import JSONConfigManager


class ConfigurableDataCollector:
    """Unified data collection framework using database-driven configurations."""
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize the configurable data collector.
        
        Parameters:
        -----------
        db_path : str
            Path to the main USGS cache database
        """
        self.db_path = db_path
        self.config_manager = JSONConfigManager(db_path=db_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'USGS-Streamflow-Dashboard/1.0 (Educational Use)'
        })
        
        # USGS API configuration
        self.base_urls = {
            'realtime': "https://waterservices.usgs.gov/nwis/iv",
            'daily': "https://waterservices.usgs.gov/nwis/dv"
        }
        self.parameter_code = "00060"  # Discharge in cubic feet per second
        
        # Rate limiting configuration
        self.rate_limit_delay = 0.5  # seconds between requests
        self.batch_size = 50  # stations per batch
        self.max_retries = 3
        
        # Logging setup
        self.setup_logging()
        
        # Collection state
        self.current_log_id = None
        self.collection_stats = {
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('data_collection.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_configuration_stations(self, config_name: str = None, config_id: int = None) -> List[Dict]:
        """
        Get stations from a configuration.
        
        Parameters:
        -----------
        config_name : str, optional
            Name of configuration to use
        config_id : int, optional
            ID of configuration to use
            
        Returns:
        --------
        List[Dict]
            List of station dictionaries with metadata
        """
        try:
            if config_name:
                config = self.config_manager.get_configuration_by_name(config_name)
                if not config:
                    raise ValueError(f"Configuration '{config_name}' not found")
            else:
                # Use default configuration
                config = self.config_manager.get_default_configuration()
                if not config:
                    raise ValueError("No default configuration found")
                config_name = config.get('config_name') or config.get('name')
            
            stations = self.config_manager.get_stations_for_configuration(config_name)
            self.logger.info(f"Retrieved {len(stations)} stations from configuration '{config_name}'")
            return stations
                
        except Exception as e:
            self.logger.error(f"Error retrieving configuration stations: {e}")
            raise
    
    def start_collection_logging(self, config_name: str, data_type: str, 
                               stations_count: int, triggered_by: str = 'manual') -> int:
        """
        Start collection logging in the database.
        
        Parameters:
        -----------
        config_name : str
            Configuration name being processed
        data_type : str
            Type of data collection ('realtime' or 'daily')
        stations_count : int
            Number of stations to be processed
        triggered_by : str
            Who/what triggered the collection
            
        Returns:
        --------
        int
            Collection log ID for tracking
        """
        try:
            log_id = self.config_manager.start_collection_log(
                config_name=config_name,
                data_type=data_type,
                stations_attempted=stations_count,
                triggered_by=triggered_by
            )
            self.current_log_id = log_id
            self.logger.info(f"Started collection log {log_id} for {stations_count} stations")
            return log_id
                
        except Exception as e:
            self.logger.error(f"Error starting collection log: {e}")
            raise
    
    def update_collection_logging(self, status: str = 'completed', error_summary: str = None):
        """Update collection logging with final results."""
        if not self.current_log_id:
            return
        
        try:
            self.config_manager.update_collection_log(
                log_id=self.current_log_id,
                stations_successful=self.collection_stats['successful'],
                stations_failed=self.collection_stats['failed'],
                status=status,
                error_summary=error_summary
            )
            
            # Log individual station errors
            for error in self.collection_stats['errors']:
                self.config_manager.log_station_error(
                    log_id=self.current_log_id,
                    station_id=error.get('station_id'),
                    error_type=error.get('error_type'),
                    error_message=error.get('error_message'),
                    http_status_code=error.get('http_status_code')
                )
            
            self.logger.info(f"Updated collection log {self.current_log_id}: "
                           f"{self.collection_stats['successful']} successful, "
                           f"{self.collection_stats['failed']} failed")
                
        except Exception as e:
            self.logger.error(f"Error updating collection log: {e}")
    
    def log_station_error(self, station: Dict, error_type: str, error_message: str, 
                         http_status_code: int = None):
        """Log an error for a specific station."""
        error_entry = {
            'station_id': station.get('id'),
            'usgs_id': station.get('usgs_id'),
            'error_type': error_type,
            'error_message': str(error_message),
            'http_status_code': http_status_code
        }
        
        self.collection_stats['errors'].append(error_entry)
        self.collection_stats['failed'] += 1
        
        self.logger.error(f"Station {station.get('usgs_id')} error ({error_type}): {error_message}")
    
    def fetch_usgs_data(self, station_ids: List[str], data_type: str, 
                       start_date: str, end_date: str) -> Tuple[pd.DataFrame, List[str]]:
        """
        Fetch data from USGS web service.
        
        Parameters:
        -----------
        station_ids : List[str]
            List of USGS station IDs
        data_type : str
            'realtime' or 'daily'
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
            
        Returns:
        --------
        Tuple[pd.DataFrame, List[str]]
            Data frame with results and list of failed station IDs
        """
        base_url = self.base_urls[data_type]
        
        # Build request parameters
        params = {
            'format': 'json',
            'sites': ','.join(station_ids),
            'parameterCd': self.parameter_code,
            'startDT': start_date,
            'endDT': end_date
        }
        
        if data_type == 'daily':
            params['statCd'] = '00003'  # Mean daily discharge
        
        failed_stations = []
        all_data = []
        
        for retry in range(self.max_retries):
            try:
                self.logger.debug(f"Fetching {data_type} data for {len(station_ids)} stations (attempt {retry + 1})")
                
                response = self.session.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Track which stations returned data in this batch
                stations_with_data = set()
                stations_without_data = set(station_ids)
                
                # Parse USGS JSON response
                if 'value' in data and 'timeSeries' in data['value']:
                    print(f"   📥 Parsing response... found {len(data['value']['timeSeries'])} time series")
                    
                    for ts_idx, ts in enumerate(data['value']['timeSeries']):
                        try:
                            site_info = ts['sourceInfo']
                            site_id = site_info['siteCode'][0]['value']
                            site_name = site_info.get('siteName', 'Unknown')
                            
                            if 'values' in ts and len(ts['values']) > 0:
                                values = ts['values'][0]['value']
                                records_before = len(all_data)
                                
                                for value in values:
                                    datetime_str = value['dateTime']
                                    discharge_str = value['value']
                                    qualifiers = value.get('qualifiers', [])
                                    
                                    # Convert datetime
                                    if data_type == 'realtime':
                                        dt = pd.to_datetime(datetime_str, utc=True)
                                    else:
                                        dt = pd.to_datetime(datetime_str)
                                    
                                    # Convert discharge value
                                    try:
                                        discharge = float(discharge_str)
                                    except (ValueError, TypeError):
                                        continue  # Skip invalid values
                                    
                                    # Determine data quality
                                    quality = 'A'  # Default approved
                                    if qualifiers:
                                        if any('P' in q for q in qualifiers):
                                            quality = 'P'  # Provisional
                                        elif any('e' in q for q in qualifiers):
                                            quality = 'E'  # Estimated
                                    
                                    all_data.append({
                                        'site_id': site_id,
                                        'datetime_utc': dt,
                                        'discharge_cfs': discharge,
                                        'data_quality': quality
                                    })
                                
                                records_added = len(all_data) - records_before
                                stations_with_data.add(site_id)
                                stations_without_data.discard(site_id)
                                
                                # Show per-station progress
                                print(f"      ✓ {site_id}: {records_added} records ({site_name[:50]})")
                            else:
                                print(f"      ⊘ {site_id}: No values returned ({site_name[:50]})")
                                stations_without_data.discard(site_id)  # Queried but no data
                            
                        except Exception as e:
                            self.logger.warning(f"Error parsing data for station: {e}")
                            print(f"      ✗ Error parsing station data: {str(e)[:60]}")
                            continue
                    
                    # Summary for this batch
                    if stations_without_data:
                        print(f"   ⚠️  {len(stations_without_data)} stations not in response: {', '.join(list(stations_without_data)[:5])}{'...' if len(stations_without_data) > 5 else ''}")
                else:
                    print(f"   ⚠️  No timeSeries data in API response")
                
                break  # Success, exit retry loop
                
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                # Extract HTTP error code if available
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    print(f"   ❌ HTTP {status_code} Error (attempt {retry + 1}/{self.max_retries})")
                    if status_code == 400:
                        print(f"      Possible reasons: Invalid station IDs, no data available for date range")
                    elif status_code == 503:
                        print(f"      USGS service temporarily unavailable")
                else:
                    print(f"   ❌ Request failed (attempt {retry + 1}/{self.max_retries}): {error_msg[:100]}")
                
                self.logger.warning(f"Request failed (attempt {retry + 1}): {e}")
                if retry == self.max_retries - 1:
                    failed_stations.extend(station_ids)
                    print(f"   ⛔ All {len(station_ids)} stations in batch marked as failed after {self.max_retries} attempts")
                else:
                    wait_time = 2 ** retry
                    print(f"   ⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)  # Exponential backoff
            
            except Exception as e:
                self.logger.error(f"Unexpected error fetching data: {e}")
                print(f"   💥 Unexpected error: {str(e)[:100]}")
                failed_stations.extend(station_ids)
                break
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        if all_data:
            df = pd.DataFrame(all_data)
            self.logger.info(f"Retrieved {len(df)} data points for {data_type} data")
            return df, failed_stations
        else:
            return pd.DataFrame(), failed_stations
    
    def process_stations_in_batches(self, stations: List[Dict], data_type: str,
                                  start_date: str, end_date: str) -> pd.DataFrame:
        """
        Process stations in batches to avoid API limits.
        
        Parameters:
        -----------
        stations : List[Dict]
            List of station dictionaries
        data_type : str
            'realtime' or 'daily'
        start_date : str
            Start date for data collection
        end_date : str
            End date for data collection
            
        Returns:
        --------
        pd.DataFrame
            Combined data from all successful stations
        """
        all_data = []
        total_batches = (len(stations) + self.batch_size - 1) // self.batch_size
        
        print(f"\n{'='*80}")
        print(f"🚀 STARTING DATA COLLECTION")
        print(f"   Total stations: {len(stations)}")
        print(f"   Batch size: {self.batch_size}")
        print(f"   Total batches: {total_batches}")
        print(f"   Data type: {data_type}")
        print(f"{'='*80}\n")
        
        # Process in batches
        for i in range(0, len(stations), self.batch_size):
            batch = stations[i:i + self.batch_size]
            batch_ids = [station['site_id'] for station in batch]
            batch_num = i//self.batch_size + 1
            
            print(f"\n{'─'*80}")
            print(f"📦 BATCH {batch_num}/{total_batches}")
            print(f"   Stations: {i+1}-{min(i+self.batch_size, len(stations))} of {len(stations)}")
            print(f"   Station IDs: {', '.join(batch_ids[:5])}{'...' if len(batch_ids) > 5 else ''}")
            print(f"   Progress: {self.collection_stats['successful']}/{self.collection_stats['attempted']} successful so far")
            print(f"{'─'*80}")
            
            self.collection_stats['attempted'] += len(batch)
            
            try:
                df, failed_ids = self.fetch_usgs_data(batch_ids, data_type, start_date, end_date)
                
                if not df.empty:
                    all_data.append(df)
                    successful_count = len(set(df['site_id'].unique()))
                    self.collection_stats['successful'] += successful_count
                    
                    print(f"✅ Batch {batch_num} SUCCESS: {successful_count} stations returned data ({len(df)} records)")
                    self.logger.info(f"Batch successful: {successful_count} stations returned data")
                
                # Log failures
                if failed_ids:
                    print(f"⚠️  Batch {batch_num} PARTIAL: {len(failed_ids)} stations failed")
                    for station in batch:
                        if station['site_id'] in failed_ids:
                            self.log_station_error(
                                station=station,
                                error_type='api_failure',
                                error_message='Failed to fetch data from USGS API'
                            )
                else:
                    if df.empty:
                        print(f"⚠️  Batch {batch_num}: No data returned from USGS API")
                
            except Exception as e:
                print(f"❌ Batch {batch_num} FAILED: {str(e)}")
                # Log all stations in batch as failed
                for station in batch:
                    self.log_station_error(
                        station=station,
                        error_type='batch_failure',
                        error_message=str(e)
                    )
                
                self.logger.error(f"Batch {i//self.batch_size + 1} failed: {e}")
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 COLLECTION SUMMARY")
        print(f"   Total stations attempted: {self.collection_stats['attempted']}")
        print(f"   Successful: {self.collection_stats['successful']}")
        print(f"   Failed: {self.collection_stats['failed']}")
        print(f"   Success rate: {(self.collection_stats['successful']/self.collection_stats['attempted']*100):.1f}%")
        print(f"{'='*80}\n")
        
        # Combine all successful data
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            print(f"✅ Combined data: {len(combined_df)} total records from {combined_df['site_id'].nunique()} unique stations\n")
            self.logger.info(f"Total data collection: {len(combined_df)} records from "
                           f"{self.collection_stats['successful']} stations")
            return combined_df
        else:
            print(f"⚠️  No data collected from any station\n")
            return pd.DataFrame()
    
    def sync_metadata_to_filters(self, stations: List[Dict]) -> int:
        """
        Sync station metadata to the filters table for dashboard use.
        This should be called after successful data collection.
        
        Parameters:
        -----------
        stations : List[Dict]
            List of station dictionaries with metadata
            
        Returns:
        --------
        int
            Number of stations synced
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            synced_count = 0
            
            for station in stations:
                usgs_id = station['site_id']
                station_name = station['station_name']
                state = station.get('state', '')
                lat = station.get('latitude')
                lon = station.get('longitude')
                huc_code = station.get('huc_code')
                drainage_area = station.get('drainage_area')
                
                # Calculate basin from HUC code
                basin = str(huc_code)[:4] if huc_code else None
                
                # Check if station exists in filters
                cursor.execute("SELECT site_id FROM filters WHERE site_id = ?", (usgs_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing record (keep calculated fields like num_water_years)
                    cursor.execute("""
                        UPDATE filters SET
                            station_name = ?,
                            latitude = ?,
                            longitude = ?,
                            state = ?,
                            huc_code = ?,
                            basin = ?,
                            drainage_area = COALESCE(?, drainage_area),
                            agency = 'USGS',
                            last_updated = ?
                        WHERE site_id = ?
                    """, (
                        station_name,
                        lat,
                        lon,
                        state,
                        huc_code,
                        basin,
                        drainage_area,
                        datetime.now().isoformat(),
                        usgs_id
                    ))
                else:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO filters (
                            site_id, station_name, latitude, longitude, state,
                            huc_code, basin, drainage_area, agency,
                            site_type, status, color, is_active, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        usgs_id,
                        station_name,
                        lat,
                        lon,
                        state,
                        huc_code,
                        basin,
                        drainage_area,
                        'USGS',
                        'Stream',
                        'active',
                        '#2E86AB',  # Blue color
                        1,  # is_active
                        datetime.now().isoformat()
                    ))
                
                synced_count += 1
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"✅ Synced metadata for {synced_count} stations to filters table")
            return synced_count
            
        except Exception as e:
            self.logger.error(f"Error syncing metadata to filters: {e}")
            return 0


def main():
    """Command-line interface for configurable data collection."""
    parser = argparse.ArgumentParser(description='Configurable USGS Data Collection')
    parser.add_argument('--config', type=str, help='Configuration name to use')
    parser.add_argument('--config-id', type=int, help='Configuration ID to use')
    parser.add_argument('--data-type', choices=['realtime', 'daily'], required=True,
                      help='Type of data to collect')
    parser.add_argument('--days', type=int, default=5,
                      help='Number of days back to collect (default: 5)')
    parser.add_argument('--db-path', type=str, default='data/usgs_data.db',
                      help='Path to database file')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without actually collecting data')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize collector
    collector = ConfigurableDataCollector(db_path=args.db_path)
    
    try:
        # Get stations from configuration
        if args.config:
            stations = collector.get_configuration_stations(config_name=args.config)
            config_name = args.config
        elif args.config_id:
            stations = collector.get_configuration_stations(config_id=args.config_id)
            config_name = f"Config ID {args.config_id}"
        else:
            stations = collector.get_configuration_stations()  # Use default
            config_name = "Default Configuration"
        
        if not stations:
            print("❌ No stations found in configuration")
            return 1
        
        print(f"🎯 Using configuration: {config_name}")
        print(f"📊 Found {len(stations)} stations to process")
        
        if args.dry_run:
            print("\n🔍 DRY RUN - Would process these stations:")
            for i, station in enumerate(stations[:10], 1):
                print(f"   {i}. {station['site_id']} - {station['station_name'][:60]}...")
            if len(stations) > 10:
                print(f"   ... and {len(stations) - 10} more stations")
            return 0
        
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
        
        print(f"📅 Data range: {start_date} to {end_date}")
        print(f"🔄 Starting {args.data_type} data collection...")
        
        # Start collection logging
        if args.config:
            config = collector.config_manager.get_configuration_by_name(args.config)
            config_name = args.config
        else:
            config = collector.config_manager.get_default_configuration()
            config_name = config.get('config_name') or config.get('name')
        
        collector.start_collection_logging(
            config_name=config_name,
            data_type=args.data_type,
            stations_count=len(stations),
            triggered_by='command_line'
        )
        
        # Process stations
        df = collector.process_stations_in_batches(
            stations=stations,
            data_type=args.data_type,
            start_date=start_date,
            end_date=end_date
        )
        
        # Store data in database
        if not df.empty:
            print(f"\n{'='*80}")
            print(f"💾 STORING DATA TO DATABASE")
            print(f"   Total records to store: {len(df)}")
            print(f"   Unique stations: {df['site_id'].nunique()}")
            print(f"{'='*80}\n")
            
            conn = sqlite3.connect(collector.db_path)
            cursor = conn.cursor()
            
            if args.data_type == 'realtime':
                # Transform for realtime_discharge table schema
                df_to_store = df[['site_id', 'datetime_utc', 'discharge_cfs']].copy()
                df_to_store['qualifiers'] = df['data_quality'] if 'data_quality' in df.columns else ''
                df_to_store['last_updated'] = datetime.now().isoformat()
                
                # Use INSERT OR REPLACE to handle duplicates gracefully
                records_inserted = 0
                records_updated = 0
                stations_processed = set()
                
                print("   Inserting records (handling duplicates)...")
                total_rows = len(df_to_store)
                last_progress = 0
                
                for idx, row in df_to_store.iterrows():
                    try:
                        # Check if record exists
                        cursor.execute("""
                            SELECT COUNT(*) FROM realtime_discharge 
                            WHERE site_id = ? AND datetime_utc = ?
                        """, (row['site_id'], row['datetime_utc']))
                        
                        exists = cursor.fetchone()[0] > 0
                        
                        # Insert or replace
                        cursor.execute("""
                            INSERT OR REPLACE INTO realtime_discharge 
                            (site_id, datetime_utc, discharge_cfs, qualifiers, last_updated)
                            VALUES (?, ?, ?, ?, ?)
                        """, (row['site_id'], row['datetime_utc'], row['discharge_cfs'], 
                              row['qualifiers'], row['last_updated']))
                        
                        if exists:
                            records_updated += 1
                        else:
                            records_inserted += 1
                        
                        stations_processed.add(row['site_id'])
                        
                        # Show progress every 10%
                        progress = int((idx + 1) / total_rows * 100)
                        if progress >= last_progress + 10:
                            print(f"      Progress: {progress}% ({idx + 1}/{total_rows} records, {len(stations_processed)} stations)")
                            last_progress = progress
                            
                    except Exception as e:
                        print(f"   ⚠️  Error inserting record for {row['site_id']}: {e}")
                        continue
                
                conn.commit()
                print(f"✅ Stored in realtime_discharge table:")
                print(f"   - New records: {records_inserted}")
                print(f"   - Updated records: {records_updated}")
                print(f"   - Total processed: {records_inserted + records_updated}")
            else:
                # Transform for streamflow_data table schema
                # For daily data, use INSERT OR REPLACE as well
                records_stored = 0
                for idx, row in df.iterrows():
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO streamflow_data 
                            (site_id, datetime_utc, discharge_cfs, qualifiers, last_updated)
                            VALUES (?, ?, ?, ?, ?)
                        """, (row['site_id'], row['datetime_utc'], row['discharge_cfs'],
                              row.get('data_quality', ''), datetime.now().isoformat()))
                        records_stored += 1
                    except Exception as e:
                        print(f"   ⚠️  Error inserting record for {row['site_id']}: {e}")
                        continue
                
                conn.commit()
                print(f"✅ Stored {records_stored} records in streamflow_data table")
            
            conn.close()
        
        # Update collection logging
        if collector.collection_stats['failed'] == 0:
            collector.update_collection_logging(status='completed')
        else:
            error_summary = f"{collector.collection_stats['failed']} stations failed"
            collector.update_collection_logging(status='completed', error_summary=error_summary)
        
        # Run metadata enrichment after successful daily data collection
        if args.data_type == 'daily' and collector.collection_stats['successful'] > 0:
            print("\n🔍 Running metadata enrichment...")
            try:
                import subprocess
                enrichment_result = subprocess.run(
                    ['python', 'enrich_station_metadata.py'],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                if enrichment_result.returncode == 0:
                    print("✅ Metadata enrichment completed successfully")
                else:
                    print(f"⚠️ Metadata enrichment had issues: {enrichment_result.stderr}")
            except subprocess.TimeoutExpired:
                print("⚠️ Metadata enrichment timed out (continuing anyway)")
            except Exception as e:
                print(f"⚠️ Could not run metadata enrichment: {e}")
        
        # Display results
        print(f"\n📊 Collection Results:")
        print(f"   ✅ Successful: {collector.collection_stats['successful']}")
        print(f"   ❌ Failed: {collector.collection_stats['failed']}")
        print(f"   📈 Data Points: {len(df) if not df.empty else 0}")
        
        if not df.empty:
            print(f"   📅 Date Range: {df['datetime_utc'].min()} to {df['datetime_utc'].max()}")
            print(f"   🏞️ Stations with Data: {df['site_id'].nunique()}")
        
        return 0 if collector.collection_stats['failed'] == 0 else 1
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        if collector.current_log_id:
            collector.update_collection_logging(status='failed', error_summary=str(e))
        return 1


if __name__ == '__main__':
    sys.exit(main())