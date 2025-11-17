#!/usr/bin/env python3
"""
Configurable Real-time USGS Discharge Data Updater

This script fetches the most recent discharge data from the USGS IV 
(instantaneous values) service using database-driven station configurations 
instead of hardcoded station lists.

Features:
- Database-driven station selection via configuration management
- Real-time progress logging visible in admin interface
- Configurable retention period and collection profiles
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
from json_config_manager import JSONConfigManager


class ConfigurableRealtimeUpdater(ConfigurableDataCollector):
    """Real-time data updater using configurable station management."""
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """Initialize the configurable real-time updater."""
        super().__init__(db_path)
        self.retention_days = 7  # Keep last 7 days of real-time data
        
    def ensure_realtime_table(self):
        """Ensure the real-time discharge table exists with proper schema."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS realtime_discharge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id TEXT NOT NULL,
                    datetime_utc TIMESTAMP NOT NULL,
                    discharge_cfs REAL NOT NULL,
                    data_quality TEXT DEFAULT 'A',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site_id, datetime_utc)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_realtime_site_datetime 
                ON realtime_discharge(site_id, datetime_utc)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_realtime_datetime 
                ON realtime_discharge(datetime_utc)
            """)
            
            conn.commit()
            conn.close()
            
            self.logger.info("Real-time discharge table ready")
            
        except Exception as e:
            self.logger.error(f"Error ensuring real-time table: {e}")
            raise
    
    def clear_old_data(self, cutoff_date: datetime):
        """Remove data older than cutoff date."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
            cursor = conn.cursor()
            
            # Convert datetime to string for SQLite compatibility
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                DELETE FROM realtime_discharge 
                WHERE datetime_utc < ?
            """, (cutoff_str,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                self.logger.info(f"Deleted {deleted_count} old real-time records (before {cutoff_date})")
            
        except Exception as e:
            self.logger.error(f"Error clearing old data: {e}")
            raise
    
    def update_realtime_data(self, df: pd.DataFrame) -> Tuple[int, int]:
        """
        Update real-time discharge data in database.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with columns: site_id, datetime_utc, discharge_cfs, data_quality
            
        Returns:
        --------
        Tuple[int, int]
            Number of records inserted and updated
        """
        if df.empty:
            return 0, 0
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
            cursor = conn.cursor()
            
            inserted_count = 0
            updated_count = 0
            
            # Process in chunks for better performance
            chunk_size = 1000
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                
                for _, row in chunk.iterrows():
                    try:
                        # Try to insert new record
                        # Convert datetime to string to avoid SQLite binding issues
                        datetime_str = row['datetime_utc'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['datetime_utc'], 'strftime') else str(row['datetime_utc'])
                        
                        cursor.execute("""
                            INSERT INTO realtime_discharge 
                            (site_id, datetime_utc, discharge_cfs, data_quality)
                            VALUES (?, ?, ?, ?)
                        """, (
                            row['site_id'],
                            datetime_str,
                            row['discharge_cfs'],
                            row['data_quality']
                        ))
                        inserted_count += 1
                        
                    except sqlite3.IntegrityError:
                        # Record exists, update it
                        datetime_str = row['datetime_utc'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['datetime_utc'], 'strftime') else str(row['datetime_utc'])
                        
                        cursor.execute("""
                            UPDATE realtime_discharge 
                            SET discharge_cfs = ?, data_quality = ?, created_at = CURRENT_TIMESTAMP
                            WHERE site_id = ? AND datetime_utc = ?
                        """, (
                            row['discharge_cfs'],
                            row['data_quality'],
                            row['site_id'],
                            datetime_str
                        ))
                        
                        if cursor.rowcount > 0:
                            updated_count += 1
                
                # Commit chunk
                conn.commit()
                
                self.logger.debug(f"Processed chunk {i//chunk_size + 1}: "
                                f"{inserted_count + updated_count} records")
            
            conn.close()
            
            self.logger.info(f"Real-time data update: {inserted_count} inserted, {updated_count} updated")
            return inserted_count, updated_count
            
        except Exception as e:
            self.logger.error(f"Error updating real-time data: {e}")
            raise
    
    def run_realtime_collection(self, config_name: str = None, config_id: int = None,
                              retention_days: int = None) -> bool:
        """
        Run complete real-time data collection process.
        
        Parameters:
        -----------
        config_name : str, optional
            Name of configuration to use
        config_id : int, optional  
            Configuration ID to use
        retention_days : int, optional
            Days of data to retain (default: 7)
            
        Returns:
        --------
        bool
            True if collection was successful
        """
        try:
            # Setup
            if retention_days:
                self.retention_days = retention_days
            
            # Ensure database table exists
            self.ensure_realtime_table()
            
            # Get stations from configuration
            stations = self.get_configuration_stations(config_name, config_id)
            
            if not stations:
                self.logger.error("No stations found in configuration")
                return False
            
            # Get configuration for logging
            if config_name:
                config = self.config_manager.get_configuration_by_name(config_name)
            else:
                config = self.config_manager.get_default_configuration()
            
            actual_config_name = config.get('config_name') or config.get('name')
            
            self.logger.info(f"🎯 Starting real-time collection: {actual_config_name}")
            self.logger.info(f"📊 Processing {len(stations)} stations")
            
            # Start collection logging
            self.start_collection_logging(
                config_name=actual_config_name,
                data_type='realtime',
                stations_count=len(stations),
                triggered_by='realtime_updater'
            )
            
            # Calculate date range (last N days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.retention_days)
            
            # Clean old data first
            self.clear_old_data(start_date)
            
            # Collect new data
            self.logger.info(f"📅 Collecting data from {start_date.date()} to {end_date.date()}")
            
            df = self.process_stations_in_batches(
                stations=stations,
                data_type='realtime',
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            # Update database
            if not df.empty:
                inserted, updated = self.update_realtime_data(df)
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
            
            # Summary
            self.logger.info("🎉 Real-time collection completed!")
            self.logger.info(f"   ✅ Successful stations: {self.collection_stats['successful']}")
            self.logger.info(f"   ❌ Failed stations: {self.collection_stats['failed']}")
            
            if not df.empty:
                self.logger.info(f"   📈 Total data points: {len(df)}")
                self.logger.info(f"   🏞️ Stations with data: {df['site_id'].nunique()}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Real-time collection failed: {e}")
            if self.current_log_id:
                self.update_collection_logging(status='failed', error_summary=str(e))
            return False


def main():
    """Command-line interface for real-time data collection."""
    parser = argparse.ArgumentParser(description='Configurable Real-time USGS Discharge Data Updater')
    parser.add_argument('--config', type=str, 
                      help='Configuration name (e.g., "Pacific Northwest Full", "Columbia River Basin")')
    parser.add_argument('--config-id', type=int, help='Configuration ID number')
    parser.add_argument('--retention-days', type=int, default=7,
                      help='Days of real-time data to retain (default: 7)')
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
            manager = JSONConfigManager(db_path=args.db_path)
            configs = manager.get_configurations()
            
            print("📋 Available Configurations:")
            print("=" * 50)
            
            for config in configs:
                name = config.get('config_name') or config.get('name')
                status = "✅ Active" if config.get('is_active', True) else "❌ Inactive"
                default = " ⭐ (Default)" if config.get('is_default', False) else ""
                print(f"{name}")
                print(f"   Status: {status}{default}")
                print(f"   Description: {config.get('description', 'No description')}")
                print()
            
            return 0
            
        except Exception as e:
            print(f"❌ Error listing configurations: {e}")
            return 1
    
    # Initialize updater
    updater = ConfigurableRealtimeUpdater(db_path=args.db_path)
    
    try:
        # Run collection
        success = updater.run_realtime_collection(
            config_name=args.config,
            config_id=args.config_id,
            retention_days=args.retention_days
        )
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Real-time update failed: {e}")
        logging.getLogger(__name__).error(f"Real-time update failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())