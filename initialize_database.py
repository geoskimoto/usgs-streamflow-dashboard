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
        
        conn.commit()
        print(f"\n✓ Database schema created successfully at: {db_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error creating database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main initialization function."""
    print("="*60)
    print("USGS Streamflow Dashboard - Database Initialization")
    print("="*60)
    print(f"Database path: {DB_PATH}")
    print()
    
    # Check if database exists
    db_exists = os.path.exists(DB_PATH)
    
    if db_exists:
        print(f"✓ Database already exists at: {DB_PATH}")
        print("  → Database is ready. No action needed.")
    else:
        print(f"✗ Database does not exist. Creating new database...")
        
        # Create the database schema
        if not create_database_schema(DB_PATH):
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
