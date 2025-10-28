#!/usr/bin/env python3
"""
Real-time USGS Discharge Data Updater

This script fetches the most recent 5 days of high-resolution discharge data 
from the USGS IV (instantaneous values) service for all active sites and 
refreshes the realtime_discharge table.

Features:
- Complete table refresh (DELETE +                 (job_name, start_time.isoformat(), datetime.now(timezone.utc).isoformat(),NSERT) for predictable data state
- Handles 15-minute resolution data from IV service
- Robust error handling with detailed logging
- Configurable retention period
- Support for manual and automated execution
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
from typing import List, Dict, Optional, Tuple
import argparse

# Add the project root to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

class RealtimeDataUpdater:
    """Manages real-time discharge data updates from USGS IV service."""
    
    def __init__(self, db_path: str = "data/usgs_cache.db"):
        """
        Initialize the real-time data updater.
        
        Parameters:
        -----------
        db_path : str
            Path to the SQLite database file
        """
        self.db_path = db_path
        self.base_url = "https://waterservices.usgs.gov/nwis/iv"
        self.parameter_code = "00060"  # Discharge in cubic feet per second
        self.retention_days = 5  # Will be read from database config
        self.session = requests.Session()
        
        # Rate limiting for USGS API
        self.api_delay = 0.5  # Seconds between requests
        self.max_sites_per_request = 20  # Batch multiple sites
        
    def get_retention_config(self) -> int:
        """Get retention days from database configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT retention_days FROM update_schedules 
                WHERE job_name = 'realtime_update'
            """)
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return 5  # Default fallback
            
        except Exception as e:
            print(f"⚠️  Warning: Could not read retention config: {e}")
            return 5
    
    def get_active_sites(self) -> List[str]:
        """Get list of active gauge sites from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use filters table (the active metadata table)
            cursor.execute("SELECT COUNT(*) FROM filters")
            filters_count = cursor.fetchone()[0]
            
            if filters_count > 0:
                # Use filters table with is_active flag
                cursor.execute("""
                    SELECT DISTINCT site_id FROM filters 
                    WHERE is_active = 1
                    ORDER BY site_id
                    LIMIT 50
                """)
                sites = [row[0] for row in cursor.fetchall()]
                print(f"📍 Found {len(sites)} active sites from filters table (limited to 50 for testing)")
            else:
                print("❌ No site data found in filters table")
                sites = []
            
            conn.close()
            return sites
            
        except Exception as e:
            print(f"❌ Error getting active sites: {e}")
            return []
    
    def fetch_iv_data_batch(self, sites: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        Fetch IV data for a batch of sites.
        
        Parameters:
        -----------
        sites : List[str]
            List of USGS site numbers
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str  
            End date in YYYY-MM-DD format
            
        Returns:
        --------
        Dict[str, pd.DataFrame]
            Dictionary mapping site_id to DataFrame of discharge data
        """
        site_data = {}
        
        # Split into smaller batches to avoid API limits
        batch_size = min(self.max_sites_per_request, len(sites))
        
        for i in range(0, len(sites), batch_size):
            batch = sites[i:i + batch_size]
            site_string = ",".join(batch)
            
            print(f"🌊 Fetching IV data for sites {i+1}-{min(i+batch_size, len(sites))} of {len(sites)}...")
            
            params = {
                'format': 'json',
                'sites': site_string,
                'startDT': start_date,
                'endDT': end_date,
                'parameterCd': self.parameter_code,
                'siteStatus': 'all'
            }
            
            try:
                response = self.session.get(self.base_url, params=params, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                
                # Parse the USGS JSON response
                if 'value' in data and 'timeSeries' in data['value']:
                    for ts in data['value']['timeSeries']:
                        site_id = ts['sourceInfo']['siteCode'][0]['value']
                        
                        # Extract time series values
                        values = []
                        if 'values' in ts and len(ts['values']) > 0:
                            for value_set in ts['values']:
                                for value in value_set.get('value', []):
                                    try:
                                        datetime_str = value['dateTime']
                                        discharge_str = value['value']
                                        quality_cd = value.get('qualifiers', [''])[0] if value.get('qualifiers') else ''
                                        
                                        # Convert to numeric, skip if invalid
                                        if discharge_str in ['-999999', '']:
                                            continue
                                            
                                        discharge = float(discharge_str)
                                        
                                        # Parse datetime (handle timezone)
                                        if 'T' in datetime_str:
                                            dt = pd.to_datetime(datetime_str, utc=True)
                                        else:
                                            dt = pd.to_datetime(datetime_str)
                                            
                                        values.append({
                                            'datetime_utc': dt,
                                            'discharge_cfs': discharge,
                                            'data_quality': quality_cd
                                        })
                                            
                                    except (ValueError, KeyError, TypeError) as e:
                                        continue  # Skip invalid records
                        
                        if values:
                            df = pd.DataFrame(values)
                            df = df.drop_duplicates(subset=['datetime_utc'])
                            df = df.sort_values('datetime_utc')
                            site_data[site_id] = df
                            print(f"   ✅ Site {site_id}: {len(df)} records")
                        else:
                            print(f"   ⚠️  Site {site_id}: No valid data")
                
                # Rate limiting
                time.sleep(self.api_delay)
                
            except requests.exceptions.RequestException as e:
                print(f"   ❌ API request failed for batch: {e}")
                continue
            except json.JSONDecodeError as e:
                print(f"   ❌ Invalid JSON response for batch: {e}")
                continue
            except Exception as e:
                print(f"   ❌ Unexpected error for batch: {e}")
                continue
        
        return site_data
    
    def refresh_realtime_table(self, site_data: Dict[str, pd.DataFrame]) -> Tuple[int, int]:
        """
        Refresh the realtime_discharge table with new data.
        
        Parameters:
        -----------
        site_data : Dict[str, pd.DataFrame]
            Dictionary mapping site_id to DataFrame of discharge data
            
        Returns:
        --------
        Tuple[int, int]
            Number of sites processed and total records inserted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clear existing real-time data
            print("🗑️  Clearing existing real-time data...")
            cursor.execute("DELETE FROM realtime_discharge")
            
            # Insert new data
            total_records = 0
            sites_processed = 0
            
            for site_id, df in site_data.items():
                if df.empty:
                    continue
                    
                # Add metadata
                df['site_no'] = site_id
                df['last_updated'] = datetime.now(timezone.utc)
                
                # Prepare data for insertion
                records = []
                for _, row in df.iterrows():
                    records.append((
                        row['site_no'],
                        row['datetime_utc'].isoformat(),
                        float(row['discharge_cfs']),
                        str(row['data_quality']),
                        row['last_updated'].isoformat()
                    ))
                
                # Batch insert
                cursor.executemany("""
                    INSERT INTO realtime_discharge 
                    (site_no, datetime_utc, discharge_cfs, data_quality, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, records)
                
                total_records += len(records)
                sites_processed += 1
                
                print(f"   ✅ Site {site_id}: {len(records)} records inserted")
            
            conn.commit()
            conn.close()
            
            print(f"✅ Real-time data refresh completed: {sites_processed} sites, {total_records} records")
            return sites_processed, total_records
            
        except Exception as e:
            print(f"❌ Error refreshing realtime table: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return 0, 0
    
    def log_execution(self, job_name: str, start_time: datetime, status: str, 
                     sites_processed: int, sites_failed: int, error_msg: str = None):
        """Log job execution details."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO job_execution_log 
                (job_name, start_time, end_time, status, sites_processed, sites_failed, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_name, start_time.isoformat(), datetime.utcnow().isoformat(),
                  status, sites_processed, sites_failed, error_msg))
            
            # Update last run time in schedules
            cursor.execute("""
                UPDATE update_schedules 
                SET last_run = ?, next_run = datetime(?, '+' || frequency_hours || ' hours')
                WHERE job_name = ?
            """, (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), job_name))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"⚠️  Warning: Could not log execution: {e}")
    
    def run_update(self) -> bool:
        """
        Run the complete real-time data update process.
        
        Returns:
        --------
        bool
            True if update completed successfully, False otherwise
        """
        start_time = datetime.now(timezone.utc)
        print(f"🚀 Starting real-time discharge data update at {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 70)
        
        try:
            # Get configuration
            self.retention_days = self.get_retention_config()
            print(f"⏰ Using retention period: {self.retention_days} days")
            
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=self.retention_days)
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            print(f"📅 Date range: {start_date_str} to {end_date_str}")
            
            # Get active sites
            sites = self.get_active_sites()
            if not sites:
                print("❌ No active sites found")
                self.log_execution('realtime_update', start_time, 'error', 0, 0, 'No active sites found')
                return False
            
            # Fetch data for all sites
            print(f"\n🌊 Fetching IV data for {len(sites)} sites...")
            site_data = self.fetch_iv_data_batch(sites, start_date_str, end_date_str)
            
            if not site_data:
                print("❌ No data retrieved from USGS API")
                self.log_execution('realtime_update', start_time, 'error', 0, len(sites), 'No data from API')
                return False
            
            # Refresh database
            print(f"\n💾 Updating database...")
            sites_processed, total_records = self.refresh_realtime_table(site_data)
            
            sites_failed = len(sites) - sites_processed
            
            # Log execution
            status = 'success' if sites_failed == 0 else 'partial'
            self.log_execution('realtime_update', start_time, status, sites_processed, sites_failed)
            
            # Summary
            duration = datetime.now(timezone.utc) - start_time
            print(f"\n🎉 Real-time data update completed!")
            print(f"   ✅ Sites processed: {sites_processed}")
            print(f"   ❌ Sites failed: {sites_failed}")
            print(f"   📊 Total records: {total_records}")
            print(f"   ⏱️  Duration: {duration.total_seconds():.1f} seconds")
            
            return sites_failed == 0
            
        except Exception as e:
            print(f"❌ Critical error during update: {e}")
            self.log_execution('realtime_update', start_time, 'error', 0, 0, str(e))
            return False

def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(description='Update real-time USGS discharge data')
    parser.add_argument('--db-path', default='data/usgs_cache.db', 
                       help='Path to SQLite database file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--dry-run', action='store_true',
                       help='Fetch data but do not update database')
    
    args = parser.parse_args()
    
    # Check if database exists
    if not os.path.exists(args.db_path):
        print(f"❌ Database not found: {args.db_path}")
        print("Please run the main application first to create the database.")
        sys.exit(1)
    
    # Run update
    updater = RealtimeDataUpdater(args.db_path)
    
    if args.dry_run:
        print("🧪 DRY RUN MODE - No database changes will be made")
        # Could add dry run logic here
        return
    
    success = updater.run_update()
    
    if success:
        print(f"\n✅ Real-time data update completed successfully")
        sys.exit(0)
    else:
        print(f"\n❌ Real-time data update failed")
        sys.exit(1)

if __name__ == '__main__':
    main()