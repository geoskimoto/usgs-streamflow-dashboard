#!/usr/bin/env python3
"""
Database Initialization Script for USGS Streamflow Dashboard

This script:
1. Checks if the unified database (usgs_data.db) exists
2. Creates the database schema if it doesn't exist
3. Can be run safely multiple times (idempotent)

The database starts empty - stations will be populated when you run
data collection for the first time using the configuration files.

Usage:
    python initialize_database.py
"""

import os
import sys
import sqlite3

# Database configuration
DB_PATH = 'usgs_data.db'

def create_database_schema(db_path: str):
    """Create the complete database schema for the unified database."""
    print(f"Creating database schema at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create stations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                site_id TEXT PRIMARY KEY,
                station_name TEXT,
                state TEXT,
                latitude REAL,
                longitude REAL,
                huc_code TEXT,
                drainage_area REAL,
                data_source TEXT,
                is_active INTEGER DEFAULT 1,
                date_added TEXT,
                last_updated TEXT
            )
        ''')
        print("✓ Created stations table")
        
        # Create configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configurations (
                config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                config_name TEXT NOT NULL,
                description TEXT,
                period_of_record_start TEXT,
                period_of_record_end TEXT,
                data_completeness REAL,
                monitoring_status TEXT,
                priority_level INTEGER,
                is_default INTEGER DEFAULT 0,
                date_created TEXT,
                last_modified TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (site_id) REFERENCES stations(site_id),
                UNIQUE(site_id, config_name)
            )
        ''')
        print("✓ Created configurations table")
        
        # Create schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id INTEGER NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                date_created TEXT,
                last_modified TEXT,
                FOREIGN KEY (config_id) REFERENCES configurations(config_id)
            )
        ''')
        print("✓ Created schedules table")
        
        # Create collection_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                collection_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                records_collected INTEGER,
                error_message TEXT,
                FOREIGN KEY (site_id) REFERENCES stations(site_id)
            )
        ''')
        print("✓ Created collection_logs table")
        
        # Create station_errors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS station_errors (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                first_occurred TEXT,
                last_occurred TEXT,
                occurrence_count INTEGER DEFAULT 1,
                is_resolved INTEGER DEFAULT 0,
                FOREIGN KEY (site_id) REFERENCES stations(site_id)
            )
        ''')
        print("✓ Created station_errors table")
        
        # Create streamflow_data table (daily values)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streamflow_data (
                site_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                mean_discharge REAL,
                min_discharge REAL,
                max_discharge REAL,
                data_quality TEXT,
                last_updated TEXT,
                PRIMARY KEY (site_id, start_date),
                FOREIGN KEY (site_id) REFERENCES stations(site_id)
            )
        ''')
        print("✓ Created streamflow_data table")
        
        # Create realtime_discharge table (15-minute values)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realtime_discharge (
                site_no TEXT NOT NULL,
                datetime_utc TEXT NOT NULL,
                discharge_cfs REAL,
                qualifiers TEXT,
                last_updated TEXT,
                PRIMARY KEY (site_no, datetime_utc)
            )
        ''')
        print("✓ Created realtime_discharge table")
        
        # Create indexes for better query performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_state ON stations(state)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_configurations_site_id ON configurations(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_configurations_active ON configurations(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedules_config_id ON schedules(config_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_collection_logs_site_id ON collection_logs(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_collection_logs_timestamp ON collection_logs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_station_errors_site_id ON station_errors(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_data_site_id ON streamflow_data(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_data_date ON streamflow_data(start_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realtime_discharge_site_no ON realtime_discharge(site_no)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realtime_discharge_datetime ON realtime_discharge(datetime_utc)')
        print("✓ Created indexes")
        
        # Create views for admin panel compatibility
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS configuration_summary AS
            SELECT 
                c.config_id as id,
                c.config_name,
                c.description,
                c.is_active,
                c.is_default,
                COUNT(DISTINCT c.site_id) as actual_station_count,
                c.date_created as created_date,
                c.last_modified,
                -- Include schedule information
                s.schedule_id,
                COALESCE(s.is_enabled, 0) as schedule_enabled,
                s.schedule_type,
                s.schedule_value,
                s.last_modified as schedule_last_modified
            FROM configurations c
            LEFT JOIN schedules s ON c.config_id = s.config_id
            GROUP BY c.config_id, c.config_name, c.description, c.is_active, c.is_default, 
                     c.date_created, c.last_modified, s.schedule_id, s.is_enabled, 
                     s.schedule_type, s.schedule_value, s.last_modified
        """)
        print("✓ Created configuration_summary view with schedule information")
        
        conn.commit()
        print(f"\n✓ Database schema created successfully at: {db_path}")
        
        # Import default configuration metadata (not stations, just config info)
        import_default_configurations(conn)
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def import_default_configurations(conn):
    """Import default configuration metadata from config files."""
    try:
        import json
        from pathlib import Path
        
        config_file = Path('config/default_configurations.json')
        
        if not config_file.exists():
            print("  → No default configurations file found. Skipping.")
            return
        
        print("\nImporting default configuration metadata...")
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        configurations = config_data.get('configurations', [])
        cursor = conn.cursor()
        
        for config in configurations:
            config_name = config.get('name')
            description = config.get('description', '')
            is_default = config.get('is_default', False)
            is_active = config.get('is_active', True)
            
            # Insert a placeholder configuration record
            # This will be populated with actual stations when data collection runs
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO configurations 
                    (site_id, config_name, description, is_default, is_active, date_created, last_modified)
                    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ''', ('__placeholder__', config_name, description, 1 if is_default else 0, 1 if is_active else 0))
                
                if cursor.rowcount > 0:
                    print(f"  ✓ Added configuration: {config_name} (default: {is_default})")
            except Exception as e:
                print(f"  ⚠ Could not add {config_name}: {e}")
        
        conn.commit()
        print(f"✓ Imported {len(configurations)} configuration entries")
        
        # Now import default schedules
        import_default_schedules(conn)
        
    except Exception as e:
        print(f"⚠ Error importing configurations: {e}")
        # Non-fatal - continue even if this fails

def import_default_schedules(conn):
    """Import default schedules from config files."""
    try:
        import json
        from pathlib import Path
        
        schedules_file = Path('config/default_schedules.json')
        
        if not schedules_file.exists():
            print("  → No default schedules file found. Skipping.")
            return
        
        print("\nImporting default schedules...")
        
        with open(schedules_file, 'r') as f:
            schedule_data = json.load(f)
        
        schedules = schedule_data.get('schedules', [])
        cursor = conn.cursor()
        
        for schedule in schedules:
            schedule_name = schedule.get('name')
            config_name = schedule.get('configuration')
            enabled = schedule.get('enabled', False)
            timing = schedule.get('timing', {})
            
            # Get the config_id for this configuration
            cursor.execute('SELECT config_id FROM configurations WHERE config_name = ? LIMIT 1', (config_name,))
            result = cursor.fetchone()
            
            if not result:
                print(f"  ⚠ Configuration '{config_name}' not found for schedule '{schedule_name}'. Skipping.")
                continue
            
            config_id = result[0]
            
            # Determine schedule type and value
            schedule_type = timing.get('type', 'cron')
            if schedule_type == 'cron':
                schedule_value = timing.get('cron_expression', '0 2 * * *')
            elif schedule_type == 'interval':
                interval_min = timing.get('interval_minutes', 60)
                schedule_value = f"{interval_min}m"
            else:
                schedule_value = timing.get('cron_expression', '0 2 * * *')
            
            # Insert schedule
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO schedules 
                    (config_id, schedule_type, schedule_value, is_enabled, date_created, last_modified)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ''', (config_id, schedule_type, schedule_value, 1 if enabled else 0))
                
                if cursor.rowcount > 0:
                    status = "enabled" if enabled else "disabled"
                    print(f"  ✓ Added schedule: {schedule_name} for '{config_name}' ({schedule_value}) - {status}")
            except Exception as e:
                print(f"  ⚠ Could not add schedule {schedule_name}: {e}")
        
        conn.commit()
        print(f"✓ Imported {len(schedules)} schedule entries")
        
    except Exception as e:
        print(f"⚠ Error importing schedules: {e}")
        # Non-fatal - continue even if this fails

def main():
    """Main initialization function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Initialize USGS Streamflow Dashboard Database'
    )
    parser.add_argument(
        '--db-path',
        default=DB_PATH,
        help=f'Path to database file (default: {DB_PATH})'
    )
    
    args = parser.parse_args()
    db_path = args.db_path
    
    print("="*60)
    print("USGS Streamflow Dashboard - Database Initialization")
    print("="*60)
    print(f"Database path: {db_path}")
    print()
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"✓ Created directory: {db_dir}")
    
    # Check if database exists
    db_exists = os.path.exists(db_path)
    
    if db_exists:
        print(f"✓ Database already exists at: {db_path}")
        print("  → Database is ready. No action needed.")
    else:
        print(f"✗ Database does not exist. Creating new database...")
        
        # Create the database schema
        if not create_database_schema(db_path):
            print("\n✗ Failed to create database schema. Exiting.")
            sys.exit(1)
        
        print("\n✓ Database initialization completed successfully!")
    
    print("\nNext steps:")
    print("  1. Review configuration files in the 'config/' folder")
    print("  2. Run data collection to populate stations:")
    print("     python configurable_data_collector.py")
    print("  3. Start the dashboard:")
    print("     python app.py")

if __name__ == '__main__':
    main()
