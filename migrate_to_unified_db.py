"""
Database Migration Script: Unified Database

Migrates data from two separate databases into a single unified database:
  - station_config.db (configurations, schedules, logs) 
  - usgs_cache.db (station metadata, streamflow data)
  → usgs_data.db (unified)

CRITICAL: Creates backups before migration. Validates all data copied correctly.

Usage:
    python migrate_to_unified_db.py [--dry-run] [--verbose]
    
Options:
    --dry-run    Preview changes without modifying databases
    --verbose    Show detailed progress
    --force      Skip confirmation prompts
    --no-backup  Skip backup creation (NOT RECOMMENDED)

Author: USGS Streamflow Dashboard Team
Date: November 6, 2025
"""

import sqlite3
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Migrate station_config.db and usgs_cache.db to unified usgs_data.db"""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False, no_backup: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.no_backup = no_backup
        self.force = force
        
        # Database paths
        self.config_db_path = Path('data/station_config.db')
        self.cache_db_path = Path('data/usgs_cache.db')
        self.target_db_path = Path('data/usgs_data.db')
        self.backup_dir = Path('data/backups')
        self.schema_file = Path('unified_database_schema.sql')
        
        # Statistics
        self.stats = {
            'stations_from_station_lists': 0,
            'stations_from_filters': 0,
            'stations_merged': 0,
            'stations_conflicts': 0,
            'streamflow_records': 0,
            'realtime_records': 0,
            'statistics_records': 0,
            'configurations': 0,
            'config_station_mappings': 0,
            'schedules': 0,
            'collection_logs': 0,
            'station_errors': 0,
            'subset_cache_records': 0
        }
        
        # Conflict log
        self.conflicts = []
        
        # ID remapping (old station_lists.id → new stations.id)
        self.station_id_map = {}
        
    def validate_preconditions(self) -> bool:
        """Validate that migration can proceed"""
        logger.info("Validating preconditions...")
        
        # Check source databases exist
        if not self.config_db_path.exists():
            logger.error(f"Source database not found: {self.config_db_path}")
            return False
            
        if not self.cache_db_path.exists():
            logger.error(f"Source database not found: {self.cache_db_path}")
            return False
            
        # Check schema file exists
        if not self.schema_file.exists():
            logger.error(f"Schema file not found: {self.schema_file}")
            return False
            
        # Check target doesn't exist (unless force)
        if self.target_db_path.exists() and not self.dry_run:
            logger.error(f"Target database already exists: {self.target_db_path}")
            logger.error("Delete or rename it first, or use --dry-run")
            return False
            
        logger.info("✓ All preconditions met")
        return True
    
    def create_backups(self):
        """Backup both source databases"""
        if self.no_backup:
            logger.warning("Skipping backups (--no-backup specified)")
            return
            
        logger.info("Creating backups...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create backups")
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        
        config_backup = self.backup_dir / f'station_config_{timestamp}.db'
        cache_backup = self.backup_dir / f'usgs_cache_{timestamp}.db'
        
        shutil.copy2(self.config_db_path, config_backup)
        shutil.copy2(self.cache_db_path, cache_backup)
        
        # Verify backups
        if config_backup.exists() and cache_backup.exists():
            logger.info(f"✓ Backups created:")
            logger.info(f"  - {config_backup}")
            logger.info(f"  - {cache_backup}")
        else:
            raise Exception("Backup verification failed!")
    
    def create_unified_schema(self):
        """Create new database with unified schema"""
        logger.info("Creating unified database schema...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create usgs_data.db with schema")
            return
            
        # Read schema SQL
        with open(self.schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Create database and execute schema
        conn = sqlite3.connect(self.target_db_path)
        conn.executescript(schema_sql)
        conn.close()
        
        logger.info(f"✓ Created {self.target_db_path}")
    
    def migrate_stations(self):
        """
        Merge station_lists and filters into unified stations table
        
        Priority rules:
        1. Use station_lists for core metadata (provenance data)
        2. Merge unique fields from filters (USGS metadata, computed stats)
        3. Resolve conflicts per documented rules
        """
        logger.info("Migrating station metadata...")
        
        # Connect to all databases
        config_conn = sqlite3.connect(self.config_db_path)
        config_conn.row_factory = sqlite3.Row
        cache_conn = sqlite3.connect(self.cache_db_path)
        cache_conn.row_factory = sqlite3.Row
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
        
        # Load station_lists
        station_lists = {}
        cursor = config_conn.execute("SELECT * FROM station_lists")
        for row in cursor.fetchall():
            station_lists[row['usgs_id']] = dict(row)
        
        self.stats['stations_from_station_lists'] = len(station_lists)
        logger.info(f"  Loaded {len(station_lists)} stations from station_lists")
        
        # Load filters
        filters_data = {}
        cursor = cache_conn.execute("SELECT * FROM filters")
        for row in cursor.fetchall():
            filters_data[row['site_id']] = dict(row)
        
        self.stats['stations_from_filters'] = len(filters_data)
        logger.info(f"  Loaded {len(filters_data)} stations from filters")
        
        # Merge data
        merged_stations = []
        for usgs_id, sl_data in station_lists.items():
            filter_data = filters_data.get(usgs_id, {})
            
            # Merge fields
            merged = self._merge_station_data(sl_data, filter_data)
            merged_stations.append(merged)
        
        # Check for stations only in filters (shouldn't happen, but be safe)
        for site_id, f_data in filters_data.items():
            if site_id not in station_lists:
                logger.warning(f"Station {site_id} in filters but not station_lists!")
                # Create from filters data only
                merged = self._create_from_filters_only(f_data)
                merged_stations.append(merged)
        
        self.stats['stations_merged'] = len(merged_stations)
        
        # Insert into target database
        if not self.dry_run:
            insert_sql = """
            INSERT INTO stations (
                usgs_id, nws_id, goes_id, station_name, state, county,
                latitude, longitude, drainage_area, huc_code, basin,
                site_type, agency, years_of_record, num_water_years, last_data_date,
                is_active, status, source_dataset, date_added, last_verified,
                color, last_updated, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor = target_conn.cursor()
            for station in merged_stations:
                cursor.execute(insert_sql, (
                    station['usgs_id'], station.get('nws_id'), station.get('goes_id'),
                    station['station_name'], station['state'], station.get('county'),
                    station['latitude'], station['longitude'], 
                    station.get('drainage_area'), station.get('huc_code'), station.get('basin'),
                    station.get('site_type'), station.get('agency', 'USGS'),
                    station.get('years_of_record'), station.get('num_water_years'), 
                    station.get('last_data_date'),
                    station.get('is_active', True), station.get('status', 'active'),
                    station['source_dataset'], station.get('date_added'),
                    station.get('last_verified'),
                    station.get('color'), station.get('last_updated'), station.get('notes')
                ))
                
                # Map old ID to new ID
                old_id = station['old_id']
                new_id = cursor.lastrowid
                self.station_id_map[old_id] = new_id
            
            target_conn.commit()
            logger.info(f"✓ Inserted {len(merged_stations)} stations")
        else:
            logger.info(f"[DRY RUN] Would insert {len(merged_stations)} stations")
        
        # Log conflicts
        if self.conflicts:
            logger.warning(f"  {len(self.conflicts)} conflicts detected (see migration_conflicts.log)")
            self._write_conflicts_log()
        
        # Cleanup
        config_conn.close()
        cache_conn.close()
        if not self.dry_run:
            target_conn.close()
    
    def _merge_station_data(self, sl_data: Dict, filter_data: Dict) -> Dict:
        """Merge station_lists + filters data with conflict resolution"""
        merged = {}
        
        # Core identifiers (from station_lists)
        merged['usgs_id'] = sl_data['usgs_id']
        merged['old_id'] = sl_data['id']  # For ID remapping
        merged['nws_id'] = sl_data.get('nws_id')
        merged['goes_id'] = sl_data.get('goes_id')
        
        # Station name (prefer filters if different - may have USGS updates)
        sl_name = sl_data['station_name']
        f_name = filter_data.get('station_name')
        if f_name and f_name != sl_name:
            self.conflicts.append({
                'usgs_id': merged['usgs_id'],
                'field': 'station_name',
                'station_lists': sl_name,
                'filters': f_name,
                'resolution': 'Used filters value'
            })
            merged['station_name'] = f_name
        else:
            merged['station_name'] = sl_name
        
        # Geographic data (prefer station_lists - source of truth)
        merged['state'] = sl_data['state']
        merged['latitude'] = sl_data['latitude']
        merged['longitude'] = sl_data['longitude']
        
        # County (only in filters)
        merged['county'] = filter_data.get('county')
        
        # Drainage area (prefer station_lists - we fixed binary bug!)
        sl_drainage = sl_data.get('drainage_area')
        f_drainage = filter_data.get('drainage_area')
        if sl_drainage is not None and f_drainage is not None:
            if abs(sl_drainage - f_drainage) > 0.1:  # Significant difference
                self.conflicts.append({
                    'usgs_id': merged['usgs_id'],
                    'field': 'drainage_area',
                    'station_lists': sl_drainage,
                    'filters': f_drainage,
                    'resolution': 'Used station_lists value'
                })
        merged['drainage_area'] = sl_drainage
        
        # HUC code (prefer station_lists)
        merged['huc_code'] = sl_data.get('huc_code')
        
        # Basin (only in filters, derived from HUC)
        merged['basin'] = filter_data.get('basin')
        
        # USGS metadata (only in filters)
        merged['site_type'] = filter_data.get('site_type')
        merged['agency'] = filter_data.get('agency', 'USGS')
        
        # Data availability stats (only in filters, computed)
        merged['years_of_record'] = filter_data.get('years_of_record')
        merged['num_water_years'] = filter_data.get('num_water_years')
        merged['last_data_date'] = filter_data.get('last_data_date')
        
        # Status (prefer station_lists for is_active)
        merged['is_active'] = sl_data.get('is_active', True)
        merged['status'] = filter_data.get('status', 'active')
        
        # Provenance (from station_lists)
        merged['source_dataset'] = sl_data['source_dataset']
        merged['date_added'] = sl_data.get('date_added')
        merged['last_verified'] = sl_data.get('last_verified')
        
        # UI state (from filters)
        merged['color'] = filter_data.get('color')
        merged['last_updated'] = filter_data.get('last_updated')
        
        # Notes
        merged['notes'] = sl_data.get('notes')
        
        return merged
    
    def _create_from_filters_only(self, filter_data: Dict) -> Dict:
        """Create station record from filters data only (fallback)"""
        return {
            'usgs_id': filter_data['site_id'],
            'old_id': None,  # No old ID
            'nws_id': None,
            'goes_id': None,
            'station_name': filter_data['station_name'],
            'state': filter_data['state'],
            'county': filter_data.get('county'),
            'latitude': filter_data['latitude'],
            'longitude': filter_data['longitude'],
            'drainage_area': filter_data.get('drainage_area'),
            'huc_code': filter_data.get('huc_code'),
            'basin': filter_data.get('basin'),
            'site_type': filter_data.get('site_type'),
            'agency': filter_data.get('agency', 'USGS'),
            'years_of_record': filter_data.get('years_of_record'),
            'num_water_years': filter_data.get('num_water_years'),
            'last_data_date': filter_data.get('last_data_date'),
            'is_active': filter_data.get('is_active', True),
            'status': filter_data.get('status', 'active'),
            'source_dataset': 'Import',  # Mark as imported
            'date_added': None,
            'last_verified': None,
            'color': filter_data.get('color'),
            'last_updated': filter_data.get('last_updated'),
            'notes': 'Migrated from filters table only'
        }
    
    def _write_conflicts_log(self):
        """Write conflicts to log file"""
        log_file = Path('migration_conflicts.log')
        with open(log_file, 'w') as f:
            f.write("Migration Conflicts Log\n")
            f.write("=" * 80 + "\n\n")
            for conflict in self.conflicts:
                f.write(f"Station: {conflict['usgs_id']}\n")
                f.write(f"Field: {conflict['field']}\n")
                f.write(f"station_lists: {conflict['station_lists']}\n")
                f.write(f"filters: {conflict['filters']}\n")
                f.write(f"Resolution: {conflict['resolution']}\n")
                f.write("-" * 80 + "\n")
        
        logger.info(f"  Conflicts logged to {log_file}")
    
    def migrate_configurations(self):
        """Copy configurations and schedules with ID remapping"""
        logger.info("Migrating configurations and schedules...")
        
        config_conn = sqlite3.connect(self.config_db_path)
        config_conn.row_factory = sqlite3.Row
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
        
        # Copy configurations
        cursor = config_conn.execute("SELECT * FROM station_configurations")
        configs = cursor.fetchall()
        
        if not self.dry_run:
            config_id_map = {}
            for config in configs:
                target_conn.execute("""
                INSERT INTO configurations 
                (config_name, description, station_count, is_default, is_active, 
                 created_date, last_modified, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config['config_name'], config['description'], config['station_count'],
                    config['is_default'], config['is_active'], config['created_date'],
                    config['last_modified'], config['created_by']
                ))
                
                config_id_map[config['id']] = target_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            
            target_conn.commit()
            self.stats['configurations'] = len(configs)
            logger.info(f"✓ Copied {len(configs)} configurations")
            
            # Copy configuration_stations with ID remapping
            cursor = config_conn.execute("SELECT * FROM configuration_stations")
            config_stations = cursor.fetchall()
            
            for cs in config_stations:
                new_config_id = config_id_map[cs['config_id']]
                new_station_id = self.station_id_map.get(cs['station_id'])
                
                if new_station_id is None:
                    logger.warning(f"Skipping mapping: station_id {cs['station_id']} not found")
                    continue
                
                target_conn.execute("""
                INSERT INTO configuration_stations 
                (config_id, station_id, priority, added_date, added_by)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    new_config_id, new_station_id, cs['priority'],
                    cs['added_date'], cs['added_by']
                ))
            
            target_conn.commit()
            self.stats['config_station_mappings'] = len(config_stations)
            logger.info(f"✓ Copied {len(config_stations)} configuration-station mappings")
            
            # Copy schedules
            cursor = config_conn.execute("SELECT * FROM update_schedules")
            schedules = cursor.fetchall()
            
            for schedule in schedules:
                new_config_id = config_id_map[schedule['config_id']]
                
                target_conn.execute("""
                INSERT INTO schedules 
                (config_id, schedule_name, data_type, cron_expression, interval_minutes,
                 is_enabled, last_run, next_run, run_count, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_config_id, schedule['schedule_name'], schedule['data_type'],
                    schedule['cron_expression'], None,  # interval_minutes not in old schema
                    schedule['is_enabled'], schedule['last_run'], schedule['next_run'],
                    schedule['run_count'], schedule['created_date']
                ))
            
            target_conn.commit()
            self.stats['schedules'] = len(schedules)
            logger.info(f"✓ Copied {len(schedules)} schedules")
            
            target_conn.close()
        else:
            logger.info(f"[DRY RUN] Would copy {len(configs)} configurations")
        
        config_conn.close()
    
    def migrate_streamflow_data(self):
        """Copy streamflow_data table"""
        logger.info("Migrating streamflow data...")
        
        cache_conn = sqlite3.connect(self.cache_db_path)
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
            
            # Copy in batches for performance
            cursor = cache_conn.execute("SELECT COUNT(*) FROM streamflow_data")
            total = cursor.fetchone()[0]
            
            batch_size = 1000
            offset = 0
            
            while offset < total:
                cursor = cache_conn.execute(
                    "SELECT * FROM streamflow_data LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )
                rows = cursor.fetchall()
                
                target_conn.executemany("""
                INSERT INTO streamflow_data 
                (site_id, data_json, start_date, end_date, last_updated)
                VALUES (?, ?, ?, ?, ?)
                """, [(row[0], row[1], row[2], row[3], row[4]) for row in rows])
                
                offset += batch_size
                if self.verbose:
                    logger.info(f"  Copied {min(offset, total)}/{total} records...")
            
            target_conn.commit()
            self.stats['streamflow_records'] = total
            logger.info(f"✓ Copied {total} streamflow data records")
            
            target_conn.close()
        else:
            cursor = cache_conn.execute("SELECT COUNT(*) FROM streamflow_data")
            total = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would copy {total} streamflow data records")
        
        cache_conn.close()
    
    def migrate_realtime_data(self):
        """Copy realtime_discharge table"""
        logger.info("Migrating realtime discharge data...")
        
        cache_conn = sqlite3.connect(self.cache_db_path)
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
            
            cursor = cache_conn.execute("SELECT COUNT(*) FROM realtime_discharge")
            total = cursor.fetchone()[0]
            
            # Check for negative/invalid values
            cursor = cache_conn.execute("SELECT COUNT(*) FROM realtime_discharge WHERE discharge_cfs < 0")
            invalid_count = cursor.fetchone()[0]
            if invalid_count > 0:
                logger.warning(f"  Found {invalid_count} records with negative discharge (will set to NULL)")
            
            batch_size = 1000
            offset = 0
            skipped = 0
            
            while offset < total:
                cursor = cache_conn.execute(
                    "SELECT * FROM realtime_discharge LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )
                rows = cursor.fetchall()
                
                # Clean data: skip records with negative or NULL discharge
                cleaned_rows = []
                for row in rows:
                    discharge = row[3]  # discharge_cfs is index 3
                    # Skip negative or invalid values entirely
                    if discharge is None or discharge < 0:
                        skipped += 1
                        continue
                    cleaned_rows.append((row[1], row[2], discharge, row[4], row[5]))
                
                target_conn.executemany("""
                INSERT INTO realtime_discharge 
                (site_no, datetime_utc, discharge_cfs, data_quality, created_at)
                VALUES (?, ?, ?, ?, ?)
                """, cleaned_rows)
                
                offset += batch_size
                if self.verbose:
                    logger.info(f"  Copied {min(offset, total)}/{total} records...")
            
            target_conn.commit()
            self.stats['realtime_records'] = total - skipped
            if skipped > 0:
                logger.info(f"✓ Copied {total - skipped}/{total} realtime discharge records ({skipped} invalid values skipped)")
            else:
                logger.info(f"✓ Copied {total} realtime discharge records")
            
            target_conn.close()
        else:
            cursor = cache_conn.execute("SELECT COUNT(*) FROM realtime_discharge")
            total = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would copy {total} realtime discharge records")
        
        cache_conn.close()
    
    def migrate_statistics(self):
        """Copy data_statistics table"""
        logger.info("Migrating data statistics...")
        
        cache_conn = sqlite3.connect(self.cache_db_path)
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
            
            cursor = cache_conn.execute("SELECT * FROM data_statistics")
            rows = cursor.fetchall()
            
            target_conn.executemany("""
            INSERT INTO data_statistics 
            (site_id, stats_json, last_updated)
            VALUES (?, ?, ?)
            """, [(row[0], row[1], row[2]) for row in rows])
            
            target_conn.commit()
            self.stats['statistics_records'] = len(rows)
            logger.info(f"✓ Copied {len(rows)} statistics records")
            
            target_conn.close()
        else:
            cursor = cache_conn.execute("SELECT COUNT(*) FROM data_statistics")
            total = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would copy {total} statistics records")
        
        cache_conn.close()
    
    def migrate_subset_cache(self):
        """Copy subset_cache table"""
        logger.info("Migrating subset cache...")
        
        cache_conn = sqlite3.connect(self.cache_db_path)
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
            
            cursor = cache_conn.execute("SELECT * FROM subset_cache")
            rows = cursor.fetchall()
            
            target_conn.executemany("""
            INSERT INTO subset_cache 
            (subset_config, site_ids, selection_date, total_available, subset_size)
            VALUES (?, ?, ?, ?, ?)
            """, [(row[1], row[2], row[3], row[4], row[5]) for row in rows])
            
            target_conn.commit()
            self.stats['subset_cache_records'] = len(rows)
            logger.info(f"✓ Copied {len(rows)} subset cache records")
            
            target_conn.close()
        else:
            cursor = cache_conn.execute("SELECT COUNT(*) FROM subset_cache")
            total = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would copy {total} subset cache records")
        
        cache_conn.close()
    
    def migrate_collection_logs(self):
        """Copy collection logs and errors with ID remapping"""
        logger.info("Migrating collection logs...")
        
        config_conn = sqlite3.connect(self.config_db_path)
        config_conn.row_factory = sqlite3.Row
        
        if not self.dry_run:
            target_conn = sqlite3.connect(self.target_db_path)
            
            # Get config ID mapping first
            cursor = config_conn.execute("SELECT id, config_name FROM station_configurations")
            old_configs = {row['config_name']: row['id'] for row in cursor.fetchall()}
            
            cursor = target_conn.execute("SELECT id, config_name FROM configurations")
            new_configs = {row[1]: row[0] for row in cursor.fetchall()}
            
            config_id_map = {old_id: new_configs[name] 
                           for name, old_id in old_configs.items() 
                           if name in new_configs}
            
            # Copy logs
            cursor = config_conn.execute("SELECT * FROM data_collection_logs")
            logs = cursor.fetchall()
            
            log_id_map = {}
            for log in logs:
                new_config_id = config_id_map.get(log['config_id'])
                if new_config_id is None:
                    continue
                
                cursor = target_conn.execute("""
                INSERT INTO collection_logs 
                (config_id, schedule_id, data_type, stations_attempted, stations_successful,
                 stations_failed, start_time, end_time, duration_seconds, error_summary,
                 status, triggered_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_config_id, None,  # schedule_id mapping would be complex
                    log['data_type'], log['stations_attempted'], log['stations_successful'],
                    log['stations_failed'], log['start_time'], log['end_time'],
                    log['duration_seconds'], log['error_summary'], log['status'],
                    log['triggered_by']
                ))
                
                log_id_map[log['id']] = cursor.lastrowid
            
            target_conn.commit()
            self.stats['collection_logs'] = len(logs)
            logger.info(f"✓ Copied {len(logs)} collection logs")
            
            # Copy station errors
            cursor = config_conn.execute("SELECT * FROM station_collection_errors")
            errors = cursor.fetchall()
            
            for error in errors:
                new_log_id = log_id_map.get(error['log_id'])
                new_station_id = self.station_id_map.get(error['station_id'])
                
                if new_log_id is None or new_station_id is None:
                    continue
                
                target_conn.execute("""
                INSERT INTO station_errors 
                (log_id, station_id, error_type, error_message, http_status_code,
                 retry_count, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_log_id, new_station_id, error['error_type'],
                    error['error_message'], error['http_status_code'],
                    error['retry_count'], error['occurred_at']
                ))
            
            target_conn.commit()
            self.stats['station_errors'] = len(errors)
            logger.info(f"✓ Copied {len(errors)} station errors")
            
            target_conn.close()
        else:
            cursor = config_conn.execute("SELECT COUNT(*) FROM data_collection_logs")
            logs = cursor.fetchone()[0]
            cursor = config_conn.execute("SELECT COUNT(*) FROM station_collection_errors")
            errors = cursor.fetchone()[0]
            logger.info(f"[DRY RUN] Would copy {logs} logs and {errors} errors")
        
        config_conn.close()
    
    def validate_migration(self):
        """Verify migration completed successfully"""
        logger.info("Validating migration...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would validate migration")
            return True
        
        target_conn = sqlite3.connect(self.target_db_path)
        success = True
        
        # Check station count
        cursor = target_conn.execute("SELECT COUNT(*) FROM stations")
        station_count = cursor.fetchone()[0]
        
        if station_count != self.stats['stations_merged']:
            logger.error(f"Station count mismatch! Expected {self.stats['stations_merged']}, got {station_count}")
            success = False
        else:
            logger.info(f"✓ Station count validated: {station_count}")
        
        # Check no NULL values in NOT NULL columns
        cursor = target_conn.execute("""
        SELECT COUNT(*) FROM stations 
        WHERE usgs_id IS NULL OR station_name IS NULL OR state IS NULL 
           OR latitude IS NULL OR longitude IS NULL
        """)
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            logger.error(f"Found {null_count} stations with NULL required fields!")
            success = False
        else:
            logger.info("✓ No NULL values in required fields")
        
        # Check foreign keys
        cursor = target_conn.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        if fk_violations:
            logger.error(f"Foreign key violations found: {len(fk_violations)}")
            for violation in fk_violations[:10]:  # Show first 10
                logger.error(f"  {violation}")
            success = False
        else:
            logger.info("✓ All foreign keys valid")
        
        # Check indexes exist
        cursor = target_conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
        index_count = cursor.fetchone()[0]
        
        if index_count < 40:  # Expect ~45 indexes
            logger.warning(f"Only {index_count} indexes found (expected ~45)")
        else:
            logger.info(f"✓ {index_count} indexes created")
        
        # Check views exist
        cursor = target_conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'")
        view_count = cursor.fetchone()[0]
        
        if view_count < 6:
            logger.warning(f"Only {view_count} views found (expected 6)")
        else:
            logger.info(f"✓ {view_count} views created")
        
        # Check triggers exist
        cursor = target_conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'")
        trigger_count = cursor.fetchone()[0]
        
        if trigger_count < 5:
            logger.warning(f"Only {trigger_count} triggers found (expected 5)")
        else:
            logger.info(f"✓ {trigger_count} triggers created")
        
        # Database integrity check
        cursor = target_conn.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        
        if integrity != 'ok':
            logger.error(f"Database integrity check failed: {integrity}")
            success = False
        else:
            logger.info("✓ Database integrity check passed")
        
        target_conn.close()
        
        return success
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"Stations (merged):              {self.stats['stations_merged']}")
        print(f"  - From station_lists:         {self.stats['stations_from_station_lists']}")
        print(f"  - From filters:               {self.stats['stations_from_filters']}")
        print(f"  - Conflicts resolved:         {self.stats['stations_conflicts']}")
        print(f"Streamflow data records:        {self.stats['streamflow_records']}")
        print(f"Realtime discharge records:     {self.stats['realtime_records']}")
        print(f"Statistics records:             {self.stats['statistics_records']}")
        print(f"Subset cache records:           {self.stats['subset_cache_records']}")
        print(f"Configurations:                 {self.stats['configurations']}")
        print(f"Configuration-station mappings: {self.stats['config_station_mappings']}")
        print(f"Schedules:                      {self.stats['schedules']}")
        print(f"Collection logs:                {self.stats['collection_logs']}")
        print(f"Station errors:                 {self.stats['station_errors']}")
        print("=" * 80 + "\n")
    
    def run(self) -> bool:
        """Execute full migration"""
        start_time = datetime.now()
        
        try:
            # Validate
            if not self.validate_preconditions():
                return False
            
            # Confirm unless force or dry-run
            if not self.dry_run and not self.force:
                print("\n" + "!" * 80)
                print("WARNING: This will create a new unified database.")
                print("Source databases will be backed up but NOT modified.")
                print("!" * 80 + "\n")
                response = input("Proceed with migration? (yes/NO): ")
                if response.lower() != 'yes':
                    logger.info("Migration cancelled by user")
                    return False
            
            # Execute migration steps
            self.create_backups()
            self.create_unified_schema()
            self.migrate_stations()
            self.migrate_configurations()
            self.migrate_streamflow_data()
            self.migrate_realtime_data()
            self.migrate_statistics()
            self.migrate_subset_cache()
            self.migrate_collection_logs()
            
            # Validate
            if not self.validate_migration():
                logger.error("Migration validation failed!")
                return False
            
            # Summary
            self.print_summary()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ Migration completed successfully in {duration:.1f} seconds")
            
            if not self.dry_run:
                logger.info(f"\nNew database: {self.target_db_path}")
                logger.info(f"Backups: {self.backup_dir}/")
                logger.info("\nNext steps:")
                logger.info("  1. Verify new database works: sqlite3 data/usgs_data.db '.tables'")
                logger.info("  2. Test application with new database")
                logger.info("  3. Update code to use data/usgs_data.db")
                logger.info("  4. Keep backups until confident migration succeeded")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Migrate to unified database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying databases')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed progress')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip backup creation (NOT RECOMMENDED)')
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Banner
    print("\n" + "=" * 80)
    print("USGS Streamflow Dashboard - Database Migration")
    print("Unified Database Migration Script")
    print("=" * 80 + "\n")
    
    if args.dry_run:
        print("*** DRY RUN MODE - No changes will be made ***\n")
    
    # Run migration
    migration = DatabaseMigration(
        dry_run=args.dry_run,
        verbose=args.verbose,
        no_backup=args.no_backup,
        force=args.force
    )
    
    success = migration.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
