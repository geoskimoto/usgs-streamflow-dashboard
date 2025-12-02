"""
Database schema setup for configurable USGS station data collection system.

This script creates the database tables needed to manage station configurations,
collection profiles, and operational monitoring for the USGS streamflow system.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path


class ConfigurationDatabaseSetup:
    """Manages database schema creation and initial setup for station configuration system."""
    
    def __init__(self, db_path="data/station_config.db"):
        """Initialize with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.connection = None
    
    def connect(self):
        """Create database connection."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        return self.connection
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def create_schema(self):
        """Create all database tables for the configuration system."""
        cursor = self.connection.cursor()
        
        print("🏗️  Creating database schema for configurable station system...")
        
        # 1. Station Lists - Master registry of all USGS stations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS station_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usgs_id TEXT UNIQUE NOT NULL,
            nws_id TEXT,
            goes_id TEXT,
            station_name TEXT NOT NULL,
            state TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            huc_code TEXT,
            drainage_area REAL,
            source_dataset TEXT NOT NULL, -- 'HADS_PNW', 'HADS_Columbia', 'Custom'
            is_active BOOLEAN DEFAULT TRUE,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_verified TIMESTAMP,
            notes TEXT
        )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_usgs_id ON station_lists(usgs_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_state ON station_lists(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_huc ON station_lists(huc_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_active ON station_lists(is_active)")
        
        # 2. Station Configurations - Collection profiles
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS station_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT UNIQUE NOT NULL,
            description TEXT,
            station_count INTEGER DEFAULT 0,
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system'
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_name ON station_configurations(config_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_active ON station_configurations(is_active)")
        
        # 3. Configuration Stations - Many-to-many relationship
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuration_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 1,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by TEXT DEFAULT 'system',
            FOREIGN KEY (config_id) REFERENCES station_configurations(id) ON DELETE CASCADE,
            FOREIGN KEY (station_id) REFERENCES station_lists(id) ON DELETE CASCADE,
            UNIQUE(config_id, station_id)
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_stations_config ON configuration_stations(config_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_stations_station ON configuration_stations(station_id)")
        
        # 4. Update Schedules - Collection job management
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            schedule_name TEXT NOT NULL,
            data_type TEXT NOT NULL CHECK (data_type IN ('realtime', 'daily', 'both')),
            cron_expression TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            run_count INTEGER DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES station_configurations(id) ON DELETE CASCADE
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_config ON update_schedules(config_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_enabled ON update_schedules(is_enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_next_run ON update_schedules(next_run)")
        
        # 5. Data Collection Logs - Operational history
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_collection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            schedule_id INTEGER,
            data_type TEXT NOT NULL CHECK (data_type IN ('realtime', 'daily', 'manual')),
            stations_attempted INTEGER DEFAULT 0,
            stations_successful INTEGER DEFAULT 0,
            stations_failed INTEGER DEFAULT 0,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds INTEGER,
            error_summary TEXT,
            status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
            triggered_by TEXT DEFAULT 'system',
            FOREIGN KEY (config_id) REFERENCES station_configurations(id),
            FOREIGN KEY (schedule_id) REFERENCES update_schedules(id)
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_config ON data_collection_logs(config_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_status ON data_collection_logs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_start_time ON data_collection_logs(start_time)")
        
        # 6. Station Collection Errors - Detailed error tracking
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS station_collection_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            error_type TEXT NOT NULL,
            error_message TEXT,
            http_status_code INTEGER,
            retry_count INTEGER DEFAULT 0,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (log_id) REFERENCES data_collection_logs(id) ON DELETE CASCADE,
            FOREIGN KEY (station_id) REFERENCES station_lists(id)
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_log ON station_collection_errors(log_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_station ON station_collection_errors(station_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_type ON station_collection_errors(error_type)")
        
        self.connection.commit()
        print("✅ Database schema created successfully")
        
        # Create views for common queries
        self.create_views()
    
    def create_views(self):
        """Create database views for common administrative queries."""
        cursor = self.connection.cursor()
        
        print("📊 Creating database views...")
        
        # Configuration summary view
        cursor.execute("""
        CREATE VIEW IF NOT EXISTS configuration_summary AS
        SELECT 
            sc.id,
            sc.config_name,
            sc.description,
            sc.is_default,
            sc.is_active,
            COUNT(cs.station_id) as actual_station_count,
            sc.station_count as recorded_count,
            sc.created_date,
            sc.last_modified
        FROM station_configurations sc
        LEFT JOIN configuration_stations cs ON sc.id = cs.config_id
        GROUP BY sc.id, sc.config_name, sc.description, sc.is_default, sc.is_active, sc.station_count, sc.created_date, sc.last_modified
        """)
        
        # Active stations by state view
        cursor.execute("""
        CREATE VIEW IF NOT EXISTS stations_by_state AS
        SELECT 
            state,
            COUNT(*) as total_stations,
            COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_stations,
            source_dataset,
            MIN(latitude) as min_lat,
            MAX(latitude) as max_lat,
            MIN(longitude) as min_lon,
            MAX(longitude) as max_lon
        FROM station_lists
        GROUP BY state, source_dataset
        ORDER BY state, source_dataset
        """)
        
        # Recent collection activity view
        cursor.execute("""
        CREATE VIEW IF NOT EXISTS recent_collection_activity AS
        SELECT 
            dcl.id,
            sc.config_name,
            dcl.data_type,
            dcl.status,
            dcl.stations_attempted,
            dcl.stations_successful,
            dcl.stations_failed,
            ROUND(dcl.duration_seconds / 60.0, 2) as duration_minutes,
            dcl.start_time,
            dcl.end_time,
            dcl.triggered_by
        FROM data_collection_logs dcl
        JOIN station_configurations sc ON dcl.config_id = sc.id
        ORDER BY dcl.start_time DESC
        LIMIT 100
        """)
        
        self.connection.commit()
        print("✅ Database views created successfully")
    
    def insert_default_configurations(self):
        """Create default station configurations based on our HADS datasets."""
        cursor = self.connection.cursor()
        
        print("🎯 Creating default station configurations...")
        
        # Pacific Northwest Full Configuration
        cursor.execute("""
        INSERT OR IGNORE INTO station_configurations 
        (config_name, description, is_default, created_by) 
        VALUES (?, ?, ?, ?)
        """, (
            "Pacific Northwest Full",
            "Complete NOAA HADS discharge monitoring stations across WA, OR, ID, MT, NV, CA (1,506 stations)",
            True,
            "system_migration"
        ))
        
        # Columbia River Basin Configuration  
        cursor.execute("""
        INSERT OR IGNORE INTO station_configurations 
        (config_name, description, is_active, created_by) 
        VALUES (?, ?, ?, ?)
        """, (
            "Columbia River Basin (HUC17)",
            "NOAA HADS discharge stations within Columbia River Basin watershed (563 stations)",
            True,
            "system_migration"
        ))
        
        # Development/Testing Configuration
        cursor.execute("""
        INSERT OR IGNORE INTO station_configurations 
        (config_name, description, is_active, created_by) 
        VALUES (?, ?, ?, ?)
        """, (
            "Development Test Set",
            "Small subset of reliable stations for development and testing (25 stations)",
            True,
            "system_migration"
        ))
        
        self.connection.commit()
        print("✅ Default configurations created")
    
    def get_schema_info(self):
        """Return information about the created database schema."""
        cursor = self.connection.cursor()
        
        # Get table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        # Get view information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
        views = cursor.fetchall()
        
        # Get configuration count
        cursor.execute("SELECT COUNT(*) FROM station_configurations")
        config_count = cursor.fetchone()[0]
        
        return {
            'tables': [t[0] for t in tables],
            'views': [v[0] for v in views],
            'configuration_count': config_count,
            'database_path': str(self.db_path)
        }


def main():
    """Main setup function to create the configuration database."""
    print("🏗️  Setting up USGS Station Configuration Database")
    print("=" * 60)
    
    # Initialize database setup
    db_setup = ConfigurationDatabaseSetup()
    
    try:
        # Connect to database
        db_setup.connect()
        
        # Create schema
        db_setup.create_schema()
        
        # Insert default configurations
        db_setup.insert_default_configurations()
        
        # Display schema information
        schema_info = db_setup.get_schema_info()
        
        print("\n📋 Database Schema Summary:")
        print("-" * 40)
        print(f"Database: {schema_info['database_path']}")
        print(f"Tables created: {len(schema_info['tables'])}")
        for table in schema_info['tables']:
            print(f"  - {table}")
        
        print(f"\nViews created: {len(schema_info['views'])}")
        for view in schema_info['views']:
            print(f"  - {view}")
        
        print(f"\nDefault configurations: {schema_info['configuration_count']}")
        
        print("\n✅ Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Run station data population script")
        print("2. Test database connections")
        print("3. Proceed to Phase 2: Admin Interface")
        
    except Exception as e:
        print(f"❌ Error during database setup: {e}")
        raise
    finally:
        db_setup.close()


if __name__ == "__main__":
    main()