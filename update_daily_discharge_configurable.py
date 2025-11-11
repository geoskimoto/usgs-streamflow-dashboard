#!/usr/bin/env python3
"""
Configurable Daily USGS Discharge Data Updater

This script fetches daily discharge data from the USGS DV (daily values) 
service using database-driven station configurations instead of hardcoded 
station lists.

Stores data in streamflow_data table (JSON blob format) compatible with the
main dashboard data_manager for visualization and analysis.

Features:
- Database-driven station selection via configuration management  
- Incremental updates (only fetches new data since last update)
- Real-time progress logging visible in admin interface
- Configurable update periods and collection profiles
- Robust error handling with detailed logging
- Support for different station configurations (PNW Full, Columbia Basin, etc.)
- Command-line configuration selection
- JSON blob storage format compatible with dashboard visualizations
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add the project root to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from configurable_data_collector import ConfigurableDataCollector
from station_config_manager import StationConfigurationManager
from enrich_station_metadata import calculate_station_statistics


class ConfigurableDailyUpdater(ConfigurableDataCollector):
    """Daily data updater using configurable station management."""
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """Initialize the configurable daily updater."""
        super().__init__(db_path)
        
    def ensure_daily_tables(self):
        """Ensure the streamflow_data table exists with proper schema."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
            cursor = conn.cursor()
            
            # Streamflow data table (JSON blob format for historical data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS streamflow_data (
                    site_id TEXT,
                    data_json TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (site_id, start_date, end_date)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_streamflow_site 
                ON streamflow_data(site_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_streamflow_dates 
                ON streamflow_data(start_date, end_date)
            """)
            
            conn.commit()
            conn.close()
            
            self.logger.info("Streamflow data tables ready")
            
        except Exception as e:
            self.logger.error(f"Error ensuring streamflow tables: {e}")
            raise
    
    def get_last_update_dates(self, station_ids: List[str]) -> Dict[str, datetime]:
        """
        Get the last data date for each station from streamflow_data table.
        Returns 1910-10-01 for new stations (full historical collection).
        
        Parameters:
        -----------
        station_ids : List[str]
            List of USGS station IDs
            
        Returns:
        --------
        Dict[str, datetime]
            Dictionary mapping station IDs to start dates for collection
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            last_dates = {}
            
            # Check streamflow_data table for each station's latest end_date
            for site_id in station_ids:
                cursor.execute("""
                    SELECT MAX(end_date) 
                    FROM streamflow_data 
                    WHERE site_id = ?
                """, (site_id,))
                
                result = cursor.fetchone()
                end_date = result[0] if result and result[0] else None
                
                if end_date:
                    # Station exists - collect from day after last end_date
                    last_date = pd.to_datetime(end_date).date()
                    # Add one day to avoid duplicate
                    next_date = last_date + timedelta(days=1)
                    last_dates[site_id] = next_date
                    self.logger.debug(f"Station {site_id}: incremental from {next_date}")
                else:
                    # New station - collect full historical record from 1910
                    historical_start = datetime(1910, 10, 1).date()
                    last_dates[site_id] = historical_start
                    self.logger.info(f"Station {site_id}: NEW - collecting full history from {historical_start}")
            
            conn.close()
            
            new_stations = sum(1 for d in last_dates.values() if d.year == 1910)
            incremental_stations = len(last_dates) - new_stations
            
            self.logger.info(f"📊 Collection strategy: {new_stations} new (full history), {incremental_stations} incremental")
            
            return last_dates
            
        except Exception as e:
            self.logger.error(f"Error getting last update dates: {e}")
            # Return historical start date (1910) for all stations on error
            historical_start = datetime(1910, 10, 1).date()
            return {site_id: historical_start for site_id in station_ids}
    
    def update_daily_data(self, df: pd.DataFrame) -> Tuple[int, int]:
        """
        Update the streamflow_data table with new daily discharge data.
        Stores data in JSON blob format compatible with data_manager.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with columns: site_id, datetime_utc, discharge_cfs, data_quality
            
        Returns:
        --------
        Tuple[int, int]
            Number of stations updated, total records processed
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Convert datetime_utc to date for daily data
            df = df.copy()
            df['date'] = pd.to_datetime(df['datetime_utc']).dt.date
            
            stations_updated = 0
            total_records = 0
            
            # Group by station for efficient processing
            for site_id, site_df in df.groupby('site_id'):
                # Sort by date
                site_df = site_df.sort_values('date')
                
                # Create JSON data structure expected by data_manager
                time_series_data = []
                for _, row in site_df.iterrows():
                    time_series_data.append({
                        'datetime': str(row['date']),
                        'discharge_cfs': float(row['discharge_cfs']) if pd.notna(row['discharge_cfs']) else None,
                        'data_quality': str(row['data_quality']) if pd.notna(row['data_quality']) else 'A'
                    })
                
                # Convert to JSON string
                data_json = json.dumps(time_series_data)
                
                # Get date range for this batch
                start_date = str(site_df['date'].min())
                end_date = str(site_df['date'].max())
                
                # Insert or replace the streamflow_data record
                cursor.execute("""
                    INSERT OR REPLACE INTO streamflow_data 
                    (site_id, data_json, start_date, end_date, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    site_id,
                    data_json,
                    start_date,
                    end_date,
                    datetime.now(timezone.utc).isoformat()
                ))
                
                stations_updated += 1
                total_records += len(site_df)
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Streamflow data update: {stations_updated} stations, {total_records} records")
            return stations_updated, total_records
            
        except Exception as e:
            self.logger.error(f"Error updating streamflow data: {e}")
            raise
    
    def run_daily_collection(self, config_name: str = None, config_id: int = None,
                           full_refresh: bool = False) -> bool:
        """
        Run complete daily data collection process with smart incremental updates.
        
        Collects historical daily values (not high-resolution data):
        - New stations: Full historical data from 1910-10-01 to present
        - Existing stations: Incremental updates from last end_date to present
        
        Parameters:
        -----------
        config_name : str, optional
            Name of configuration to use
        config_id : int, optional  
            Configuration ID to use
        full_refresh : bool
            If True, force full historical collection for all stations (1910-present)
            regardless of existing data.
            
        Returns:
        --------
        bool
            True if collection was successful
        """
        try:
            # Ensure database tables exist
            self.ensure_daily_tables()
            
            # Get stations from configuration
            stations = self.get_configuration_stations(config_name, config_id)
            
            if not stations:
                self.logger.error("No stations found in configuration")
                return False
            
            # Get configuration for logging
            with self.config_manager as manager:
                if config_name:
                    config = manager.get_configuration_by_name(config_name)
                elif config_id:
                    # Get config info
                    configs = manager.get_configurations(active_only=False)
                    config = next((c for c in configs if c['id'] == config_id), None)
                    if not config:
                        config = {'id': config_id, 'config_name': f'Config {config_id}'}
                else:
                    config = manager.get_default_configuration()
            
            self.logger.info(f"🎯 Starting daily collection: {config['config_name']}")
            self.logger.info(f"📊 Processing {len(stations)} stations")
            
            # Start collection logging
            self.start_collection_logging(
                config_id=config['id'],
                data_type='daily',
                stations_count=len(stations),
                triggered_by='daily_updater'
            )
            
            # Determine collection strategy
            station_ids = [station['usgs_id'] for station in stations]
            last_dates = self.get_last_update_dates(station_ids)
            
            if full_refresh:
                # Full refresh: collect all available data from 1910
                start_date = datetime(1910, 10, 1)
                end_date = datetime.now()
                self.logger.info(f"📅 Full refresh: collecting from {start_date.date()} to {end_date.date()}")
            else:
                # Smart incremental update
                # Use the earliest start date to capture all new/updated data
                earliest_date = min(last_dates.values())
                end_date = datetime.now()
                
                # For historical backfill: use 1910 if any new stations
                has_new_stations = any(d.year == 1910 for d in last_dates.values())
                
                if has_new_stations:
                    start_date = datetime(1910, 10, 1)
                    new_count = sum(1 for d in last_dates.values() if d.year == 1910)
                    self.logger.info(f"📅 Historical backfill: {new_count} new stations - collecting from 1910")
                else:
                    start_date = earliest_date
                    self.logger.info(f"📅 Incremental update from {start_date} to {end_date.date()}")
                
                self.logger.info(f"   Earliest station start: {earliest_date}")
                self.logger.info(f"   Latest station start: {max(last_dates.values())}")
            
            # Collect data
            df = self.process_stations_in_batches(
                stations=stations,
                data_type='daily',
                start_date=start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            # Update database
            if not df.empty:
                inserted, updated = self.update_daily_data(df)
                self.logger.info(f"💾 Database update: {inserted} new, {updated} updated records")
            else:
                self.logger.warning("No data retrieved from USGS service")
            
            # Finalize logging
            success = self.collection_stats['failed'] == 0
            status = 'completed' if success else 'completed_with_errors'
            error_summary = None
            
            if self.collection_stats['failed'] > 0:
                error_summary = (f"{self.collection_stats['failed']} stations failed. "
                               f"Check logs for details.")
            
            self.update_collection_logging(status=status, error_summary=error_summary)
            
            # Sync metadata to filters table for dashboard
            if success and stations:
                self.logger.info("🔄 Syncing station metadata to filters table...")
                synced = self.sync_metadata_to_filters(stations)
                if synced > 0:
                    self.logger.info(f"   ✅ Synced {synced} stations to filters table")
                
                # Calculate statistics (years_of_record, num_water_years) from collected data
                self.logger.info("📊 Calculating station statistics from historical data...")
                try:
                    stats_updated = calculate_station_statistics(
                        cache_db_path=self.db_path,
                        logger=self.logger,
                        quiet=False
                    )
                    if stats_updated > 0:
                        self.logger.info(f"   ✅ Updated statistics for {stats_updated} stations")
                except Exception as e:
                    self.logger.warning(f"   ⚠️ Statistics calculation failed: {e}")
            
            # Summary
            self.logger.info("🎉 Daily collection completed!")
            self.logger.info(f"   ✅ Successful stations: {self.collection_stats['successful']}")
            self.logger.info(f"   ❌ Failed stations: {self.collection_stats['failed']}")
            
            if not df.empty:
                self.logger.info(f"   📈 Total data points: {len(df)}")
                self.logger.info(f"   🏞️ Stations with data: {df['site_id'].nunique()}")
                date_range = df['datetime_utc']
                self.logger.info(f"   📅 Data date range: {date_range.min().date()} to {date_range.max().date()}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Daily collection failed: {e}")
            if self.current_log_id:
                self.update_collection_logging(status='failed', error_summary=str(e))
            return False


def main():
    """Command-line interface for daily data collection."""
    parser = argparse.ArgumentParser(description='Configurable Daily USGS Discharge Data Updater')
    parser.add_argument('--config', type=str, 
                      help='Configuration name (e.g., "Pacific Northwest Full", "Columbia River Basin")')
    parser.add_argument('--config-id', type=int, help='Configuration ID number')
    parser.add_argument('--full-refresh', action='store_true',
                      help='Perform full refresh (re-collect all historical data from 1910)')
    parser.add_argument('--db-path', type=str, default='data/usgs_data.db',
                      help='Path to database file (default: data/usgs_data.db)')
    parser.add_argument('--list-configs', action='store_true',
                      help='List available configurations and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List configurations if requested
    if args.list_configs:
        try:
            with StationConfigurationManager() as manager:
                configs = manager.get_configurations()
                
                print("📋 Available Configurations:")
                print("=" * 50)
                
                for config in configs:
                    status = "✅ Active" if config['is_active'] else "❌ Inactive"
                    default = " ⭐ (Default)" if config['is_default'] else ""
                    print(f"ID: {config['id']} - {config['config_name']}")
                    print(f"   Stations: {config['actual_station_count']}")
                    print(f"   Status: {status}{default}")
                    print(f"   Description: {config['description'] or 'No description'}")
                    print()
                
                return 0
                
        except Exception as e:
            print(f"❌ Error listing configurations: {e}")
            return 1
    
    # Initialize updater
    updater = ConfigurableDailyUpdater(db_path=args.db_path)
    
    try:
        # Run collection
        success = updater.run_daily_collection(
            config_name=args.config,
            config_id=args.config_id,
            full_refresh=args.full_refresh
        )
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Daily update failed: {e}")
        logging.getLogger(__name__).error(f"Daily update failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())