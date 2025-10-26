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

from station_config_manager import StationConfigurationManager


class ConfigurableDataCollector:
    """Unified data collection framework using database-driven configurations."""
    
    def __init__(self, db_path: str = "data/usgs_cache.db"):
        """
        Initialize the configurable data collector.
        
        Parameters:
        -----------
        db_path : str
            Path to the main USGS cache database
        """
        self.db_path = db_path
        self.config_manager = StationConfigurationManager()
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
            with self.config_manager as manager:
                if config_name:
                    config = manager.get_configuration_by_name(config_name)
                    if not config:
                        raise ValueError(f"Configuration '{config_name}' not found")
                    config_id = config['id']
                elif config_id:
                    pass  # Use provided config_id
                else:
                    # Use default configuration
                    config = manager.get_default_configuration()
                    if not config:
                        raise ValueError("No default configuration found")
                    config_id = config['id']
                
                stations = manager.get_stations_for_configuration(config_id)
                self.logger.info(f"Retrieved {len(stations)} stations from configuration ID {config_id}")
                return stations
                
        except Exception as e:
            self.logger.error(f"Error retrieving configuration stations: {e}")
            raise
    
    def start_collection_logging(self, config_id: int, data_type: str, 
                               stations_count: int, triggered_by: str = 'manual') -> int:
        """
        Start collection logging in the database.
        
        Parameters:
        -----------
        config_id : int
            Configuration ID being processed
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
            with self.config_manager as manager:
                log_id = manager.start_collection_log(
                    config_id=config_id,
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
            with self.config_manager as manager:
                manager.update_collection_log(
                    log_id=self.current_log_id,
                    stations_successful=self.collection_stats['successful'],
                    stations_failed=self.collection_stats['failed'],
                    status=status,
                    error_summary=error_summary
                )
                
                # Log individual station errors
                for error in self.collection_stats['errors']:
                    manager.log_station_error(
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
                
                # Parse USGS JSON response
                if 'value' in data and 'timeSeries' in data['value']:
                    for ts in data['value']['timeSeries']:
                        try:
                            site_info = ts['sourceInfo']
                            site_no = site_info['siteCode'][0]['value']
                            
                            if 'values' in ts and len(ts['values']) > 0:
                                values = ts['values'][0]['value']
                                
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
                                        'site_no': site_no,
                                        'datetime_utc': dt,
                                        'discharge_cfs': discharge,
                                        'data_quality': quality
                                    })
                            
                        except Exception as e:
                            self.logger.warning(f"Error parsing data for station: {e}")
                            continue
                
                break  # Success, exit retry loop
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request failed (attempt {retry + 1}): {e}")
                if retry == self.max_retries - 1:
                    failed_stations.extend(station_ids)
                else:
                    time.sleep(2 ** retry)  # Exponential backoff
            
            except Exception as e:
                self.logger.error(f"Unexpected error fetching data: {e}")
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
        
        # Process in batches
        for i in range(0, len(stations), self.batch_size):
            batch = stations[i:i + self.batch_size]
            batch_ids = [station['usgs_id'] for station in batch]
            
            self.logger.info(f"Processing batch {i//self.batch_size + 1}: "
                           f"stations {i+1}-{min(i+self.batch_size, len(stations))} of {len(stations)}")
            
            self.collection_stats['attempted'] += len(batch)
            
            try:
                df, failed_ids = self.fetch_usgs_data(batch_ids, data_type, start_date, end_date)
                
                if not df.empty:
                    all_data.append(df)
                    successful_count = len(set(df['site_no'].unique()))
                    self.collection_stats['successful'] += successful_count
                    
                    self.logger.info(f"Batch successful: {successful_count} stations returned data")
                
                # Log failures
                if failed_ids:
                    for station in batch:
                        if station['usgs_id'] in failed_ids:
                            self.log_station_error(
                                station=station,
                                error_type='api_failure',
                                error_message='Failed to fetch data from USGS API'
                            )
                
            except Exception as e:
                # Log all stations in batch as failed
                for station in batch:
                    self.log_station_error(
                        station=station,
                        error_type='batch_failure',
                        error_message=str(e)
                    )
                
                self.logger.error(f"Batch {i//self.batch_size + 1} failed: {e}")
        
        # Combine all successful data
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Total data collection: {len(combined_df)} records from "
                           f"{self.collection_stats['successful']} stations")
            return combined_df
        else:
            return pd.DataFrame()


def main():
    """Command-line interface for configurable data collection."""
    parser = argparse.ArgumentParser(description='Configurable USGS Data Collection')
    parser.add_argument('--config', type=str, help='Configuration name to use')
    parser.add_argument('--config-id', type=int, help='Configuration ID to use')
    parser.add_argument('--data-type', choices=['realtime', 'daily'], required=True,
                      help='Type of data to collect')
    parser.add_argument('--days', type=int, default=5,
                      help='Number of days back to collect (default: 5)')
    parser.add_argument('--db-path', type=str, default='data/usgs_cache.db',
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
                print(f"   {i}. {station['usgs_id']} - {station['station_name'][:60]}...")
            if len(stations) > 10:
                print(f"   ... and {len(stations) - 10} more stations")
            return 0
        
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
        
        print(f"📅 Data range: {start_date} to {end_date}")
        print(f"🔄 Starting {args.data_type} data collection...")
        
        # Start collection logging (get config ID from first station's association)
        with collector.config_manager as manager:
            if args.config:
                config = manager.get_configuration_by_name(args.config)
            elif args.config_id:
                config = {'id': args.config_id}
            else:
                config = manager.get_default_configuration()
            
            collector.start_collection_logging(
                config_id=config['id'],
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
        
        # Update collection logging
        if collector.collection_stats['failed'] == 0:
            collector.update_collection_logging(status='completed')
        else:
            error_summary = f"{collector.collection_stats['failed']} stations failed"
            collector.update_collection_logging(status='completed', error_summary=error_summary)
        
        # Display results
        print(f"\n📊 Collection Results:")
        print(f"   ✅ Successful: {collector.collection_stats['successful']}")
        print(f"   ❌ Failed: {collector.collection_stats['failed']}")
        print(f"   📈 Data Points: {len(df) if not df.empty else 0}")
        
        if not df.empty:
            print(f"   📅 Date Range: {df['datetime_utc'].min()} to {df['datetime_utc'].max()}")
            print(f"   🏞️ Stations with Data: {df['site_no'].nunique()}")
        
        return 0 if collector.collection_stats['failed'] == 0 else 1
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        if collector.current_log_id:
            collector.update_collection_logging(status='failed', error_summary=str(e))
        return 1


if __name__ == '__main__':
    sys.exit(main())