"""
Simple script to import stations from CSV files into the unified database.
Works with the new usgs_data.db schema.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime


def import_stations_from_csv(db_path="data/usgs_data.db"):
    """Import stations from CSV files into the database."""
    
    print("🚀 Importing Stations into Unified Database")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # CSV files to import
    csv_files = [
        ("pnw_usgs_discharge_stations_hads.csv", "HADS_PNW"),
        ("columbia_basin_hads_stations.csv", "HADS_Columbia")
    ]
    
    total_added = 0
    total_updated = 0
    
    for csv_file, source_dataset in csv_files:
        if not Path(csv_file).exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping...")
            continue
        
        print(f"\n📂 Loading {csv_file} (source: {source_dataset})")
        df = pd.read_csv(csv_file)
        print(f"   Found {len(df)} stations in CSV")
        
        added = 0
        updated = 0
        
        for _, row in df.iterrows():
            try:
                # Prepare station data
                usgs_id = str(row['usgs_id']).strip()
                station_name = str(row['station_name']).strip()
                state = str(row['state_code']).strip()
                latitude = float(row['latitude_decimal'])
                longitude = float(row['longitude_decimal'])
                huc_code = str(row.get('huc_cd', '')).strip() if pd.notna(row.get('huc_cd')) else None
                drainage_area = float(row['drainage_area']) if pd.notna(row.get('drainage_area')) else None
                nws_id = str(row.get('nws_id', '')).strip() if pd.notna(row.get('nws_id')) else None
                goes_id = str(row.get('goes_id', '')).strip() if pd.notna(row.get('goes_id')) else None
                
                # Check if station exists
                cursor.execute("SELECT site_id FROM stations WHERE site_id = ?", (usgs_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing station
                    cursor.execute("""
                    UPDATE stations 
                    SET station_name = ?, state = ?, latitude = ?, longitude = ?,
                        huc_code = ?, drainage_area = ?, source_dataset = ?,
                        nws_id = ?, goes_id = ?, last_updated = ?
                    WHERE site_id = ?
                    """, (station_name, state, latitude, longitude, huc_code, 
                          drainage_area, source_dataset, nws_id, goes_id,
                          datetime.now().isoformat(), usgs_id))
                    updated += 1
                else:
                    # Insert new station
                    cursor.execute("""
                    INSERT INTO stations 
                    (site_id, station_name, state, latitude, longitude, huc_code,
                     drainage_area, source_dataset, nws_id, goes_id, is_active,
                     date_added, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (usgs_id, station_name, state, latitude, longitude, huc_code,
                          drainage_area, source_dataset, nws_id, goes_id,
                          datetime.now().isoformat(), datetime.now().isoformat()))
                    added += 1
                    
            except Exception as e:
                print(f"   ⚠️  Error importing station {row.get('usgs_id', 'unknown')}: {e}")
                continue
        
        conn.commit()
        print(f"   ✅ Processed: {added} added, {updated} updated")
        total_added += added
        total_updated += updated
    
    # Configuration linking is now handled by config_loader.py
    # The configurations table uses a many-to-many relationship via configuration_stations
    print(f"\n✓ Station import complete!")
    print(f"   Total stations in database: {total_added + total_updated}")
    print(f"\n📝 Next steps:")
    print(f"   1. Run: python config_loader.py")
    print(f"   2. This will link stations to configurations based on config/default_configurations.json")
    
    # Update Development Test Set with first 25 stations
    cursor.execute("""
    UPDATE configurations
    SET site_id = (SELECT GROUP_CONCAT(site_id) FROM (SELECT site_id FROM stations LIMIT 25))
    WHERE config_name = 'Development Test Set'
    """)
    
    conn.commit()
    
    # Print summary
    print(f"\n📊 Import Summary")
    print("=" * 60)
    cursor.execute("SELECT COUNT(*) FROM stations")
    total_stations = cursor.fetchone()[0]
    print(f"Total stations in database: {total_stations}")
    print(f"  • Added: {total_added}")
    print(f"  • Updated: {total_updated}")
    
    cursor.execute("SELECT state, COUNT(*) FROM stations GROUP BY state")
    print(f"\nStations by state:")
    for state, count in cursor.fetchall():
        print(f"  • {state}: {count} stations")
    
    conn.close()
    print(f"\n✅ Import completed successfully!")


if __name__ == "__main__":
    import_stations_from_csv()
