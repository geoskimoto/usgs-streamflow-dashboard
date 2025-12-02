#!/usr/bin/env python3
"""
Database Schema Updater for Real-time Data Enhancement

This script adds new tables to support the dual-script architecture:
1. realtime_discharge - High resolution data (last 5 days)
2. update_schedules - Configuration for automated update jobs
"""

import sqlite3
import os
from datetime import datetime

def update_database_schema():
    """Add new tables to support real-time data and scheduling."""
    
    # Database path
    db_path = "data/usgs_cache.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("Please run the main app first to create the initial database.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔧 Updating database schema for real-time data support...")
        
        # 1. Create realtime_discharge table
        print("📊 Creating realtime_discharge table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realtime_discharge (
                site_id TEXT,
                datetime_utc TIMESTAMP,
                discharge_cfs REAL,
                data_quality TEXT,        -- 'P' (provisional), 'A' (approved), etc.
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (site_id, datetime_utc)
            )
        ''')
        
        # Create index for faster queries on site_id
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_realtime_site_datetime 
            ON realtime_discharge(site_id, datetime_utc DESC)
        ''')
        
        print("✅ realtime_discharge table created")
        
        # 2. Create update_schedules table
        print("⏰ Creating update_schedules table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_schedules (
                job_name TEXT PRIMARY KEY,           -- 'daily_update', 'realtime_update'
                frequency_hours INTEGER,             -- How often to run (in hours)
                last_run TIMESTAMP,                  -- When last executed
                next_run TIMESTAMP,                  -- When next scheduled
                enabled BOOLEAN DEFAULT TRUE,        -- Is job active
                retention_days INTEGER DEFAULT 5,   -- For realtime: days to keep
                description TEXT,                    -- Human readable description
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        print("✅ update_schedules table created")
        
        # 3. Initialize default schedule configurations
        print("📝 Inserting default schedule configurations...")
        
        # Default schedules
        default_schedules = [
            {
                'job_name': 'realtime_update',
                'frequency_hours': 2,  # Every 2 hours
                'retention_days': 5,
                'description': 'Updates high-resolution discharge data (last 5 days) from USGS IV service'
            },
            {
                'job_name': 'daily_update', 
                'frequency_hours': 12,  # Every 12 hours
                'retention_days': 0,  # Not applicable for daily data
                'description': 'Updates historical daily discharge data from USGS DV service'
            }
        ]
        
        for schedule in default_schedules:
            cursor.execute('''
                INSERT OR IGNORE INTO update_schedules 
                (job_name, frequency_hours, retention_days, description)
                VALUES (?, ?, ?, ?)
            ''', (schedule['job_name'], schedule['frequency_hours'], 
                  schedule['retention_days'], schedule['description']))
        
        print("✅ Default schedules initialized")
        
        # 4. Create job execution log table for monitoring
        print("📋 Creating job_execution_log table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_execution_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT,  -- 'success', 'error', 'partial'
                sites_processed INTEGER DEFAULT 0,
                sites_failed INTEGER DEFAULT 0,
                error_message TEXT,
                execution_details TEXT  -- JSON with additional details
            )
        ''')
        
        # Create index for log queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_job_log_name_time 
            ON job_execution_log(job_name, start_time DESC)
        ''')
        
        print("✅ job_execution_log table created")
        
        # 5. Check existing tables and show summary
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\n📋 Database schema updated successfully!")
        print(f"📊 Total tables: {len(tables)}")
        
        # Show the new tables
        new_tables = ['realtime_discharge', 'update_schedules', 'job_execution_log']
        for table_name in new_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table_name}: {count} records")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Database schema update completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error updating database schema: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def verify_schema():
    """Verify the new tables were created correctly."""
    db_path = "data/usgs_cache.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n🔍 Verifying database schema...")
        
        # Check each new table
        required_tables = {
            'realtime_discharge': ['site_id', 'datetime_utc', 'discharge_cfs', 'data_quality'],
            'update_schedules': ['job_name', 'frequency_hours', 'enabled', 'retention_days'],
            'job_execution_log': ['job_name', 'start_time', 'status', 'sites_processed']
        }
        
        for table_name, required_columns in required_tables.items():
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not cursor.fetchone():
                print(f"❌ Table '{table_name}' not found")
                continue
                
            # Check columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [column[1] for column in cursor.fetchall()]
            
            missing_columns = set(required_columns) - set(columns)
            if missing_columns:
                print(f"❌ Table '{table_name}' missing columns: {missing_columns}")
            else:
                print(f"✅ Table '{table_name}' verified ({len(columns)} columns)")
        
        conn.close()
        print("✅ Schema verification completed")
        
    except Exception as e:
        print(f"❌ Error verifying schema: {e}")

if __name__ == '__main__':
    print("🚀 USGS Dashboard Database Schema Updater")
    print("=" * 50)
    
    # Update schema
    success = update_database_schema()
    
    if success:
        # Verify the changes
        verify_schema()
        print(f"\n💡 Next steps:")
        print(f"   1. Run the real-time data updater script")
        print(f"   2. Configure cron jobs for automated updates")
        print(f"   3. Update admin panel to manage schedules")
    else:
        print(f"\n❌ Schema update failed. Please check error messages above.")