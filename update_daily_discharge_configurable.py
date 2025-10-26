#!/usr/bin/env python3
"""
Configurable Daily USGS Discharge Data Updater

This script fetches daily discharge data from the USGS DV (daily values) 
service using database-driven station configurations instead of hardcoded 
station lists.

Features:
- Database-driven station selection via configuration management  
- Incremental updates (only fetches new data since last update)
- Real-time progress logging visible in admin interface
- Configurable update periods and collection profiles
- Robust error handling with detailed logging
- Support for different station configurations (PNW Full, Columbia Basin, etc.)
- Command-line configuration selection
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
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


class ConfigurableDailyUpdater(ConfigurableDataCollector):
    """Daily data updater using configurable station management."""
    
    def __init__(self, db_path: str = "data/usgs_cache.db"):
        """Initialize the configurable daily updater."""
        super().__init__(db_path)
        
    def ensure_daily_tables(self):
        """Ensure the daily discharge tables exist with proper schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Main streamflow data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS streamflow_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_no TEXT NOT NULL,
                    datetime DATE NOT NULL,
                    discharge_cfs REAL,
                    data_quality TEXT DEFAULT 'A',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site_no, datetime)
                )
            """)
            
            # Update tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_update_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_no TEXT NOT NULL,
                    last_update_date DATE NOT NULL,
                    last_data_date DATE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site_no)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_streamflow_site_datetime 
                ON streamflow_data(site_no, datetime)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_streamflow_datetime 
                ON streamflow_data(datetime)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_log_site 
                ON daily_update_log(site_no)
            """)
            
            conn.commit()
            conn.close()
            
            self.logger.info("Daily discharge tables ready")
            
        except Exception as e:
            self.logger.error(f"Error ensuring daily tables: {e}")
            raise
    
    def get_last_update_dates(self, station_ids: List[str]) -> Dict[str, datetime]:
        """
        Get the last update date for each station.
        
        Parameters:
        -----------
        station_ids : List[str]
            List of USGS station IDs
            
        Returns:
        --------
        Dict[str, datetime]
            Dictionary mapping station IDs to last update dates
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last update dates from log
            placeholders = ','.join(['?'] * len(station_ids))
            cursor.execute(f"""
                SELECT site_no, last_data_date, last_update_date
                FROM daily_update_log 
                WHERE site_no IN ({placeholders})
            """, station_ids)
            
            results = cursor.fetchall()
            
            last_dates = {}
            for site_no, last_data_date, last_update_date in results:
                # Use the most recent data date, or fall back to 30 days ago if new station
                if last_data_date:
                    last_dates[site_no] = pd.to_datetime(last_data_date).date()
                else:
                    # New station, start from 30 days ago
                    last_dates[site_no] = (datetime.now() - timedelta(days=30)).date()
            
            # For stations not in log, start from 30 days ago
            for site_no in station_ids:
                if site_no not in last_dates:
                    last_dates[site_no] = (datetime.now() - timedelta(days=30)).date()
            
            conn.close()
            
            self.logger.debug(f"Retrieved last update dates for {len(last_dates)} stations")
            return last_dates
            
        except Exception as e:
            self.logger.error(f"Error getting last update dates: {e}")
            # Return default dates (30 days ago) for all stations
            default_date = (datetime.now() - timedelta(days=30)).date()
            return {site_no: default_date for site_no in station_ids}
    
    def update_daily_data(self, df: pd.DataFrame) -> Tuple[int, int]:
        """
        Update daily discharge data in database.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with columns: site_no, datetime_utc, discharge_cfs, data_quality
            
        Returns:
        --------
        Tuple[int, int]
            Number of records inserted and updated
        """
        if df.empty:
            return 0, 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert datetime_utc to date for daily data
            df = df.copy()
            df['date'] = pd.to_datetime(df['datetime_utc']).dt.date
            
            inserted_count = 0
            updated_count = 0
            
            # Group by station for efficient processing
            for site_no, site_df in df.groupby('site_no'):
                # Sort by date to get latest data
                site_df = site_df.sort_values('date')
                
                for _, row in site_df.iterrows():
                    try:
                        # Try to insert new record
                        cursor.execute("""
                            INSERT INTO streamflow_data 
                            (site_no, datetime, discharge_cfs, data_quality)
                            VALUES (?, ?, ?, ?)
                        """, (
                            row['site_no'],
                            row['date'],
                            row['discharge_cfs'],
                            row['data_quality']
                        ))
                        inserted_count += 1
                        
                    except sqlite3.IntegrityError:
                        # Record exists, update it if data is different
                        cursor.execute("""
                            UPDATE streamflow_data 
                            SET discharge_cfs = ?, data_quality = ?, created_at = CURRENT_TIMESTAMP
                            WHERE site_no = ? AND datetime = ?
                            AND (discharge_cfs != ? OR data_quality != ?)
                        """, (
                            row['discharge_cfs'],
                            row['data_quality'],
                            row['site_no'],
                            row['date'],
                            row['discharge_cfs'],
                            row['data_quality']
                        ))
                        
                        if cursor.rowcount > 0:
                            updated_count += 1
                
                # Update the daily log with latest data date
                latest_date = site_df['date'].max()
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_update_log
                    (site_no, last_update_date, last_data_date)
                    VALUES (?, DATE('now'), ?)
                """, (site_no, latest_date))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Daily data update: {inserted_count} inserted, {updated_count} updated")
            return inserted_count, updated_count
            
        except Exception as e:
            self.logger.error(f"Error updating daily data: {e}")
            raise
    
    def run_daily_collection(self, config_name: str = None, config_id: int = None,
                           days_back: int = None, full_refresh: bool = False) -> bool:
        """
        Run complete daily data collection process.
        
        Parameters:
        -----------
        config_name : str, optional
            Name of configuration to use
        config_id : int, optional  
            Configuration ID to use
        days_back : int, optional
            Maximum days back to collect (default: 30)
        full_refresh : bool
            If True, collect all available data (ignores last update dates)
            
        Returns:
        --------
        bool
            True if collection was successful
        """
        try:
            # Setup
            if days_back is None:
                days_back = 30
            
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
            
            if full_refresh:
                # Full refresh: collect all available data
                start_date = datetime(1900, 1, 1)
                end_date = datetime.now()
                self.logger.info(f"📅 Full refresh: collecting all available data")
            else:
                # Incremental update: collect since last update
                last_dates = self.get_last_update_dates(station_ids)
                
                # Find the earliest start date
                earliest_date = min(last_dates.values())
                # Ensure we don't go back more than specified days
                cutoff_date = (datetime.now() - timedelta(days=days_back)).date()
                start_date = max(earliest_date, cutoff_date)
                end_date = datetime.now()
                
                self.logger.info(f"📅 Incremental update from {start_date} to {end_date.date()}")
                self.logger.info(f"   Earliest station last update: {earliest_date}")
                self.logger.info(f"   Latest station last update: {max(last_dates.values())}")
            
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
            
            # Summary
            self.logger.info("🎉 Daily collection completed!")
            self.logger.info(f"   ✅ Successful stations: {self.collection_stats['successful']}")
            self.logger.info(f"   ❌ Failed stations: {self.collection_stats['failed']}")
            
            if not df.empty:
                self.logger.info(f"   📈 Total data points: {len(df)}")
                self.logger.info(f"   🏞️ Stations with data: {df['site_no'].nunique()}")
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
    parser.add_argument('--days-back', type=int, default=30,
                      help='Maximum days back to collect (default: 30)')
    parser.add_argument('--full-refresh', action='store_true',
                      help='Perform full refresh (collect all available data)')
    parser.add_argument('--db-path', type=str, default='data/usgs_cache.db',
                      help='Path to database file (default: data/usgs_cache.db)')
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
            days_back=args.days_back,
            full_refresh=args.full_refresh
        )
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Daily update failed: {e}")
        logging.getLogger(__name__).error(f"Daily update failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())