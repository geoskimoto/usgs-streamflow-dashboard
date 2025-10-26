"""
Populate station configuration database with NOAA HADS station data.

This script imports the refined station lists (PNW full and Columbia Basin)
into the configuration database and creates the default station configurations.
"""

import sqlite3
import pandas as pd
import csv
from pathlib import Path
from datetime import datetime


class StationDataPopulator:
    """Populates the configuration database with HADS station data."""
    
    def __init__(self, db_path="data/station_config.db"):
        """Initialize with database path."""
        self.db_path = Path(db_path)
        self.connection = None
    
    def connect(self):
        """Create database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def load_hads_stations(self, csv_file, source_dataset):
        """Load HADS stations from CSV file into database."""
        print(f"📂 Loading stations from {csv_file} (source: {source_dataset})")
        
        if not Path(csv_file).exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping...")
            return 0
        
        # Read CSV file
        try:
            df = pd.read_csv(csv_file)
            print(f"   Found {len(df)} stations in CSV")
        except Exception as e:
            print(f"❌ Error reading {csv_file}: {e}")
            return 0
        
        # Validate required columns (check for actual column names in CSV)
        required_cols = ['usgs_id', 'station_name', 'state_code', 'latitude_decimal', 'longitude_decimal']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"❌ Missing required columns: {missing_cols}")
            print(f"   Available columns: {list(df.columns)}")
            return 0
        
        cursor = self.connection.cursor()
        stations_added = 0
        stations_updated = 0
        
        for _, row in df.iterrows():
            try:
                # Prepare station data
                station_data = {
                    'usgs_id': str(row['usgs_id']).strip(),
                    'nws_id': str(row.get('nws_id', '')).strip() if pd.notna(row.get('nws_id')) else None,
                    'goes_id': str(row.get('goes_id', '')).strip() if pd.notna(row.get('goes_id')) else None,
                    'station_name': str(row['station_name']).strip(),
                    'state': str(row['state_code']).strip(),
                    'latitude': float(row['latitude_decimal']),
                    'longitude': float(row['longitude_decimal']),
                    'huc_code': str(row.get('huc_cd', '')).strip() if pd.notna(row.get('huc_cd')) else None,
                    'drainage_area': float(row['drainage_area']) if pd.notna(row.get('drainage_area')) else None,
                    'source_dataset': source_dataset
                }
                
                # Check if station already exists
                cursor.execute("SELECT id FROM station_lists WHERE usgs_id = ?", (station_data['usgs_id'],))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing station
                    cursor.execute("""
                    UPDATE station_lists SET
                        nws_id = ?, goes_id = ?, station_name = ?, state = ?,
                        latitude = ?, longitude = ?, huc_code = ?, drainage_area = ?,
                        source_dataset = ?, last_verified = CURRENT_TIMESTAMP
                    WHERE usgs_id = ?
                    """, (
                        station_data['nws_id'], station_data['goes_id'], 
                        station_data['station_name'], station_data['state'],
                        station_data['latitude'], station_data['longitude'],
                        station_data['huc_code'], station_data['drainage_area'],
                        station_data['source_dataset'], station_data['usgs_id']
                    ))
                    stations_updated += 1
                else:
                    # Insert new station
                    cursor.execute("""
                    INSERT INTO station_lists 
                    (usgs_id, nws_id, goes_id, station_name, state, latitude, longitude, 
                     huc_code, drainage_area, source_dataset, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        station_data['usgs_id'], station_data['nws_id'], 
                        station_data['goes_id'], station_data['station_name'], 
                        station_data['state'], station_data['latitude'], 
                        station_data['longitude'], station_data['huc_code'], 
                        station_data['drainage_area'], station_data['source_dataset']
                    ))
                    stations_added += 1
                
            except Exception as e:
                print(f"⚠️  Error processing station {row.get('usgs_id', 'unknown')}: {e}")
                continue
        
        self.connection.commit()
        print(f"✅ Processed {len(df)} stations: {stations_added} added, {stations_updated} updated")
        return stations_added + stations_updated
    
    def create_configuration_mappings(self):
        """Create mappings between configurations and stations."""
        cursor = self.connection.cursor()
        
        print("🔗 Creating configuration-station mappings...")
        
        # Get configuration IDs
        cursor.execute("SELECT id, config_name FROM station_configurations")
        configs = dict(cursor.fetchall())
        
        pnw_config_id = None
        columbia_config_id = None
        test_config_id = None
        
        for config_id, config_name in configs.items():
            if "Pacific Northwest" in config_name:
                pnw_config_id = config_id
            elif "Columbia River Basin" in config_name:
                columbia_config_id = config_id
            elif "Development Test" in config_name:
                test_config_id = config_id
        
        # Map PNW Full configuration (all HADS_PNW stations)
        if pnw_config_id:
            print(f"   Mapping PNW Full configuration (ID: {pnw_config_id})")
            cursor.execute("""
            INSERT OR IGNORE INTO configuration_stations (config_id, station_id, priority)
            SELECT ?, id, 1
            FROM station_lists 
            WHERE source_dataset IN ('HADS_PNW', 'HADS_Columbia')
            """, (pnw_config_id,))
            
            pnw_count = cursor.rowcount
            
            # Update station count
            cursor.execute("""
            UPDATE station_configurations 
            SET station_count = (
                SELECT COUNT(*) FROM configuration_stations WHERE config_id = ?
            ), last_modified = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (pnw_config_id, pnw_config_id))
            
            print(f"   ✅ PNW Full: {pnw_count} stations mapped")
        
        # Map Columbia Basin configuration (only HADS_Columbia stations)
        if columbia_config_id:
            print(f"   Mapping Columbia Basin configuration (ID: {columbia_config_id})")
            cursor.execute("""
            INSERT OR IGNORE INTO configuration_stations (config_id, station_id, priority)
            SELECT ?, id, 1
            FROM station_lists 
            WHERE source_dataset = 'HADS_Columbia'
            """, (columbia_config_id,))
            
            columbia_count = cursor.rowcount
            
            # Update station count
            cursor.execute("""
            UPDATE station_configurations 
            SET station_count = (
                SELECT COUNT(*) FROM configuration_stations WHERE config_id = ?
            ), last_modified = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (columbia_config_id, columbia_config_id))
            
            print(f"   ✅ Columbia Basin: {columbia_count} stations mapped")
        
        # Create test configuration with sample stations
        if test_config_id:
            print(f"   Creating test configuration (ID: {test_config_id})")
            cursor.execute("""
            INSERT OR IGNORE INTO configuration_stations (config_id, station_id, priority)
            SELECT ?, id, 1
            FROM station_lists 
            WHERE source_dataset = 'HADS_Columbia'
            AND state IN ('WA', 'OR')
            ORDER BY usgs_id
            LIMIT 25
            """, (test_config_id,))
            
            test_count = cursor.rowcount
            
            # Update station count
            cursor.execute("""
            UPDATE station_configurations 
            SET station_count = (
                SELECT COUNT(*) FROM configuration_stations WHERE config_id = ?
            ), last_modified = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (test_config_id, test_config_id))
            
            print(f"   ✅ Test Set: {test_count} stations mapped")
        
        self.connection.commit()
        print("✅ Configuration mappings completed")
    
    def create_default_schedules(self):
        """Create default update schedules for configurations."""
        cursor = self.connection.cursor()
        
        print("⏰ Creating default update schedules...")
        
        # Get active configurations
        cursor.execute("SELECT id, config_name FROM station_configurations WHERE is_active = 1")
        configs = cursor.fetchall()
        
        for config_id, config_name in configs:
            if "Development Test" in config_name:
                # Test configuration - manual updates only
                continue
            
            # Real-time updates every 15 minutes
            cursor.execute("""
            INSERT OR IGNORE INTO update_schedules 
            (config_id, schedule_name, data_type, cron_expression, is_enabled)
            VALUES (?, ?, ?, ?, ?)
            """, (
                config_id,
                f"{config_name} - Realtime (15min)",
                "realtime",
                "*/15 * * * *",  # Every 15 minutes
                True
            ))
            
            # Daily updates at 6 AM
            cursor.execute("""
            INSERT OR IGNORE INTO update_schedules 
            (config_id, schedule_name, data_type, cron_expression, is_enabled)
            VALUES (?, ?, ?, ?, ?)
            """, (
                config_id,
                f"{config_name} - Daily (6 AM)",
                "daily",
                "0 6 * * *",  # Daily at 6 AM
                True
            ))
        
        self.connection.commit()
        print("✅ Default schedules created")
    
    def generate_summary_report(self):
        """Generate a summary report of the populated database."""
        cursor = self.connection.cursor()
        
        print("\n📊 Database Population Summary")
        print("=" * 50)
        
        # Station counts by source
        cursor.execute("""
        SELECT source_dataset, COUNT(*) as station_count, COUNT(DISTINCT state) as state_count
        FROM station_lists 
        GROUP BY source_dataset
        ORDER BY station_count DESC
        """)
        
        print("\nStations by Source Dataset:")
        for source, count, states in cursor.fetchall():
            print(f"  {source}: {count} stations ({states} states)")
        
        # Configuration summary
        cursor.execute("SELECT * FROM configuration_summary ORDER BY config_name")
        configs = cursor.fetchall()
        
        print(f"\nConfigurations Created: {len(configs)}")
        for config in configs:
            print(f"  {config[1]}: {config[5]} stations ({'Default' if config[3] else 'Custom'})")
        
        # Schedule summary
        cursor.execute("""
        SELECT sc.config_name, us.data_type, COUNT(*) as schedule_count
        FROM update_schedules us
        JOIN station_configurations sc ON us.config_id = sc.id
        GROUP BY sc.config_name, us.data_type
        ORDER BY sc.config_name, us.data_type
        """)
        
        schedules = cursor.fetchall()
        print(f"\nSchedules Created: {len(schedules)}")
        for config_name, data_type, count in schedules:
            print(f"  {config_name} - {data_type}: {count} schedules")
        
        # State distribution
        cursor.execute("SELECT * FROM stations_by_state ORDER BY state, source_dataset")
        states = cursor.fetchall()
        
        print(f"\nGeographic Distribution: {len(states)} state-source combinations")
        for state_info in states[:10]:  # Show first 10
            state, total, active, source = state_info[:4]
            print(f"  {state} ({source}): {active}/{total} active stations")
        
        if len(states) > 10:
            print(f"  ... and {len(states) - 10} more")


def main():
    """Main function to populate the station configuration database."""
    print("🚀 Populating USGS Station Configuration Database")
    print("=" * 55)
    
    populator = StationDataPopulator()
    
    try:
        # Connect to database
        populator.connect()
        
        # Load HADS station data
        total_stations = 0
        
        # Load PNW full dataset
        pnw_count = populator.load_hads_stations(
            "pnw_usgs_discharge_stations_hads.csv", 
            "HADS_PNW"
        )
        total_stations += pnw_count
        
        # Load Columbia Basin dataset  
        columbia_count = populator.load_hads_stations(
            "columbia_basin_hads_stations.csv",
            "HADS_Columbia"
        )
        total_stations += columbia_count
        
        print(f"\n📈 Total stations processed: {total_stations}")
        
        # Create configuration mappings
        populator.create_configuration_mappings()
        
        # Create default schedules
        populator.create_default_schedules()
        
        # Generate summary report
        populator.generate_summary_report()
        
        print("\n✅ Database population completed successfully!")
        print("\nThe configuration database is ready for:")
        print("  - Admin interface development (Phase 2)")
        print("  - Configurable update scripts (Phase 3)")
        print("  - Production deployment")
        
    except Exception as e:
        print(f"❌ Error during database population: {e}")
        raise
    finally:
        populator.close()


if __name__ == "__main__":
    main()