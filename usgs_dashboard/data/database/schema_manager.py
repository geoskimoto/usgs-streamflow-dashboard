"""
Database Schema Management

Handles database schema creation, verification, and migrations.
Consolidates logic from initialize_database.py and update_database_schema.py.
"""

import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .connection import DatabaseConnection


class SchemaManager:
    """
    Manages database schema creation, verification, and migrations.
    
    Usage:
        schema_mgr = SchemaManager("data/usgs_data.db")
        schema_mgr.initialize_database()
        schema_mgr.verify_schema()
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize schema manager.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        """
        self.db = DatabaseConnection(db_path)
        self.schema_file = "unified_database_schema.sql"
        
    def initialize_database(self, force: bool = False) -> bool:
        """
        Initialize database with complete schema.
        
        Parameters:
        -----------
        force : bool
            If True, drop existing tables and recreate
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        if self.db.database_exists() and not force:
            print(f"✓ Database already exists: {self.db.db_path}")
            return self.verify_schema()
        
        if force and self.db.database_exists():
            print(f"⚠️  Force mode: Recreating database")
        
        # Try to load schema from SQL file
        if os.path.exists(self.schema_file):
            return self._create_from_sql_file()
        else:
            print(f"⚠️  Schema file not found: {self.schema_file}")
            print(f"⚠️  Using inline schema...")
            return self._create_inline_schema()
    
    def _create_from_sql_file(self) -> bool:
        """Create schema from unified_database_schema.sql file."""
        print(f"📄 Loading schema from: {self.schema_file}")
        
        try:
            with open(self.schema_file, 'r') as f:
                schema_sql = f.read()
            
            with self.db.get_connection() as conn:
                conn.executescript(schema_sql)
            
            print(f"✅ Database schema created from {self.schema_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error creating schema from file: {e}")
            return False
    
    def _create_inline_schema(self) -> bool:
        """Fallback: Create schema inline if SQL file not found."""
        print(f"📝 Creating inline database schema")
        
        try:
            with self.db.get_connection() as conn:
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Create stations table
                conn.execute('''
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
                
                # Create indexes for stations
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stations_site_id ON stations(site_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stations_state ON stations(state)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stations_active ON stations(is_active)')
                
                # Create streamflow_data table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS streamflow_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        site_id TEXT NOT NULL,
                        data_json TEXT,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES stations(site_id) ON DELETE CASCADE,
                        UNIQUE(site_id, start_date, end_date)
                    )
                ''')
                
                conn.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_site ON streamflow_data(site_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_streamflow_dates ON streamflow_data(start_date, end_date)')
                
                # Create realtime_discharge table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS realtime_discharge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        site_id TEXT NOT NULL,
                        datetime_utc TIMESTAMP NOT NULL,
                        discharge_cfs REAL NOT NULL,
                        data_quality TEXT DEFAULT 'A',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES stations(site_id) ON DELETE CASCADE,
                        UNIQUE(site_id, datetime_utc)
                    )
                ''')
                
                conn.execute('CREATE INDEX IF NOT EXISTS idx_realtime_site_datetime ON realtime_discharge(site_id, datetime_utc)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_realtime_datetime ON realtime_discharge(datetime_utc)')
                
                # Create subset_cache table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS subset_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subset_config TEXT NOT NULL,
                        site_ids TEXT NOT NULL,
                        selection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_available INTEGER,
                        subset_size INTEGER
                    )
                ''')
                
                # Create collection_logs table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS collection_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_name TEXT NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        status TEXT DEFAULT 'running',
                        stations_attempted INTEGER DEFAULT 0,
                        stations_successful INTEGER DEFAULT 0,
                        stations_failed INTEGER DEFAULT 0,
                        error_message TEXT,
                        metadata TEXT
                    )
                ''')
                
                # Create filters table (for backward compatibility)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS filters (
                        site_id TEXT PRIMARY KEY,
                        station_name TEXT,
                        latitude REAL,
                        longitude REAL,
                        state TEXT,
                        county TEXT,
                        drainage_area REAL,
                        huc_code TEXT,
                        basin TEXT,
                        site_type TEXT,
                        num_water_years INTEGER,
                        last_data_date TEXT,
                        is_active BOOLEAN,
                        color TEXT,
                        last_updated TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES stations(site_id) ON DELETE CASCADE
                    )
                ''')
                
            print(f"✅ Inline schema created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating inline schema: {e}")
            return False
    
    def verify_schema(self) -> bool:
        """
        Verify that all required tables exist.
        
        Returns:
        --------
        bool
            True if all required tables exist, False otherwise
        """
        required_tables = {
            'stations',
            'streamflow_data',
            'realtime_discharge'
        }
        
        try:
            existing_tables = set(self.db.get_table_names())
            missing_tables = required_tables - existing_tables
            
            if missing_tables:
                print(f"❌ Missing required tables: {missing_tables}")
                return False
            
            print(f"✅ All required tables exist")
            return True
            
        except Exception as e:
            print(f"❌ Error verifying schema: {e}")
            return False
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column information for a table.
        
        Parameters:
        -----------
        table_name : str
            Name of the table
            
        Returns:
        --------
        List[Dict]
            List of column information dictionaries
        """
        query = f"PRAGMA table_info({table_name})"
        results = self.db.execute_query(query, fetch='all')
        
        columns = []
        for row in results:
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default_value': row[4],
                'primary_key': bool(row[5])
            })
        
        return columns
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get comprehensive database information.
        
        Returns:
        --------
        Dict
            Database statistics and information
        """
        info = {
            'exists': self.db.database_exists(),
            'path': self.db.db_path,
            'size_bytes': self.db.get_database_size(),
            'tables': {}
        }
        
        if info['exists']:
            for table_name in self.db.get_table_names():
                info['tables'][table_name] = {
                    'row_count': self.db.get_table_row_count(table_name),
                    'columns': self.get_table_info(table_name)
                }
        
        return info
    
    def add_column(self, table_name: str, column_name: str, 
                   column_type: str, default_value: Any = None) -> bool:
        """
        Add a new column to an existing table.
        
        Parameters:
        -----------
        table_name : str
            Name of the table
        column_name : str
            Name of the new column
        column_type : str
            SQL data type for the column
        default_value : Any
            Default value for existing rows
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            # Check if column already exists
            columns = self.get_table_info(table_name)
            if any(col['name'] == column_name for col in columns):
                print(f"✓ Column {column_name} already exists in {table_name}")
                return True
            
            # Build ALTER TABLE statement
            default_clause = ""
            if default_value is not None:
                if isinstance(default_value, str):
                    default_clause = f" DEFAULT '{default_value}'"
                else:
                    default_clause = f" DEFAULT {default_value}"
            
            query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{default_clause}"
            
            with self.db.get_connection() as conn:
                conn.execute(query)
            
            print(f"✅ Added column {column_name} to {table_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            return False
    
    def vacuum_database(self):
        """Vacuum the database to reclaim space."""
        print("🧹 Vacuuming database...")
        self.db.vacuum()
        print("✅ Database vacuumed")
    
    def reindex_database(self):
        """Rebuild all database indexes."""
        print("🔧 Reindexing database...")
        self.db.reindex()
        print("✅ Database reindexed")
