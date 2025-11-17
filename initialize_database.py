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
    
    # Use the unified schema SQL file
    schema_file = 'unified_database_schema.sql'
    
    if not os.path.exists(schema_file):
        print(f"✗ Schema file not found: {schema_file}")
        print("  Using inline schema instead...")
        return create_inline_schema(db_path)
    
    print(f"✓ Loading schema from: {schema_file}")
    
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Execute the complete schema
        cursor.executescript(schema_sql)
        print("✓ Database schema created from unified_database_schema.sql")
        
        conn.commit()
        print(f"\n✓ Database schema created successfully at: {db_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def create_inline_schema(db_path: str):
    """Fallback: Create schema inline if SQL file is not found."""
    print(f"Creating inline database schema at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create stations table (unified schema)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT UNIQUE NOT NULL,
                nws_id TEXT,
                goes_id TEXT,
                station_name TEXT NOT NULL,
                state TEXT NOT NULL,
                county TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                drainage_area REAL,
                huc_code TEXT,
                basin TEXT,
                site_type TEXT,
                agency TEXT DEFAULT 'USGS',
                years_of_record INTEGER,
                num_water_years INTEGER,
                last_data_date TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'active',
                source_dataset TEXT NOT NULL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified TIMESTAMP,
                color TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')
        print("✓ Created stations table")
        
        # Create collection_logs table (unified schema - config tables removed, uses config_name string)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_name TEXT NOT NULL,
                data_type TEXT NOT NULL,
                stations_attempted INTEGER DEFAULT 0,
                stations_successful INTEGER DEFAULT 0,
                stations_failed INTEGER DEFAULT 0,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration_seconds INTEGER,
                error_summary TEXT,
                status TEXT NOT NULL,
                triggered_by TEXT DEFAULT 'system'
            )
        ''')
        print("✓ Created collection_logs table")
        
        # Create station_errors table (unified schema)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS station_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                station_id INTEGER NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                http_status_code INTEGER,
                retry_count INTEGER DEFAULT 0,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (log_id) REFERENCES collection_logs(id) ON DELETE CASCADE,
                FOREIGN KEY (station_id) REFERENCES stations(id)
            )
        ''')
        print("✓ Created station_errors table")
        
        # Create streamflow_data table (unified schema - daily values)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streamflow_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                data_json TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
                UNIQUE(site_id, start_date, end_date)
            )
        ''')
        print("✓ Created streamflow_data table")
        
        # Create realtime_discharge table (unified schema - 15-minute values)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realtime_discharge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                datetime_utc TIMESTAMP NOT NULL,
                discharge_cfs REAL NOT NULL,
                data_quality TEXT DEFAULT 'A',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
                UNIQUE(site_id, datetime_utc)
            )
        ''')
        print("✓ Created realtime_discharge table")
        
        # Create data_statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                stats_json TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
                UNIQUE(site_id)
            )
        ''')
        print("✓ Created data_statistics table")
        
        # Create subset_cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subset_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subset_config TEXT NOT NULL,
                site_ids TEXT NOT NULL,
                selection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_available INTEGER,
                subset_size INTEGER
            )
        ''')
        print("✓ Created subset_cache table")
        
        # Create indexes for better query performance (unified schema)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_site_id ON stations(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_state ON stations(state)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_basin ON stations(basin)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_huc ON stations(huc_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_active ON stations(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_source ON stations(source_dataset)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_config_name ON collection_logs(config_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_start_time ON collection_logs(start_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_errors_log ON station_errors(log_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_errors_station ON station_errors(station_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_site ON streamflow_data(site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_dates ON streamflow_data(start_date, end_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realtime_site_datetime ON realtime_discharge(site_id, datetime_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realtime_datetime ON realtime_discharge(datetime_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_statistics_site ON data_statistics(site_id)')
        print("✓ Created indexes")
        
        # Create views for admin panel monitoring (unified schema - config tables removed)
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS recent_collection_activity AS
            SELECT 
                cl.id,
                cl.config_name,
                cl.data_type,
                cl.status,
                cl.stations_attempted,
                cl.stations_successful,
                cl.stations_failed,
                ROUND(cl.duration_seconds / 60.0, 2) as duration_minutes,
                cl.start_time,
                cl.end_time,
                cl.triggered_by
            FROM collection_logs cl
            ORDER BY cl.start_time DESC
            LIMIT 100
        """)
        print("✓ Created recent_collection_activity view")
        
        # Create stations_with_realtime view
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS stations_with_realtime AS
            SELECT DISTINCT
                s.id,
                s.site_id,
                s.station_name,
                s.state,
                s.latitude,
                s.longitude,
                MAX(rd.datetime_utc) as last_realtime_update
            FROM stations s
            JOIN realtime_discharge rd ON s.site_id = rd.site_id
            WHERE rd.datetime_utc > datetime('now', '-24 hours')
            GROUP BY s.id, s.site_id, s.station_name, s.state, s.latitude, s.longitude
        """)
        print("✓ Created stations_with_realtime view")
        
        conn.commit()
        print(f"\n✓ Inline database schema created successfully at: {db_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating inline database schema: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()



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
