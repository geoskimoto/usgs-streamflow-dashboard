#!/usr/bin/env python3
"""
Import Southwest states (UT, AZ, CO) stations into the unified database.
Works with the new repository pattern and usgs_data.db schema.
"""

import sys
from pathlib import Path
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from usgs_dashboard.data.database import (
    DatabaseConnection,
    StationRepository,
    SchemaManager
)


def import_southwest_stations():
    """Import Southwest states stations from CSV into database."""
    
    print("🚀 Importing Southwest States Stations")
    print("=" * 60)
    
    db_path = "data/usgs_data.db"
    csv_file = "data/southwest_discharge_stations.csv"
    
    # Check if CSV exists
    if not Path(csv_file).exists():
        print(f"❌ Error: {csv_file} not found!")
        return False
    
    # Initialize database connection and repositories
    db_conn = DatabaseConnection(db_path)
    schema_mgr = SchemaManager(db_path)
    station_repo = StationRepository(db_path)
    
    # Ensure database is initialized
    print("\n📊 Verifying database schema...")
    if not schema_mgr.verify_schema():
        print("⚙️  Initializing database schema...")
        schema_mgr.initialize_database()
    
    # Load CSV file
    print(f"\n📂 Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"   Found {len(df)} stations in CSV")
    
    # Show state breakdown
    print("\n📍 Stations by state:")
    for state, count in df['state_cd'].value_counts().items():
        print(f"   {state}: {count}")
    
    # Prepare stations for bulk import
    print("\n📥 Preparing stations for import...")
    stations = []
    
    for _, row in df.iterrows():
        try:
            station = {
                'site_id': str(row['site_no']).strip(),
                'station_name': str(row['station_nm']).strip(),
                'state': str(row['state_cd']).strip(),
                'latitude': float(row['latitude']) if pd.notna(row['latitude']) else None,
                'longitude': float(row['longitude']) if pd.notna(row['longitude']) else None,
                'huc_code': str(row['huc_code']).strip() if pd.notna(row['huc_code']) else None,
                'drainage_area': float(row['drainage_area']) if pd.notna(row['drainage_area']) else None,
                'source_dataset': row.get('basin', 'Southwest'),
                'is_active': 1
            }
            stations.append(station)
        except Exception as e:
            print(f"   ⚠️  Skipping station {row.get('site_no', 'unknown')}: {e}")
            continue
    
    print(f"   Prepared {len(stations)} stations for import")
    
    # Convert to DataFrame for bulk import
    stations_df = pd.DataFrame(stations)
    
    # Bulk import using repository
    print("\n💾 Importing stations into database...")
    result = station_repo.bulk_upsert_stations(stations_df)
    
    # Handle different return types from bulk_upsert_stations
    if isinstance(result, tuple):
        added, updated = result
    else:
        added = result
        updated = 0
    
    print("\n" + "=" * 60)
    print("✅ Import Complete!")
    print(f"   Added: {added} new stations")
    print(f"   Updated: {updated} existing stations")
    print(f"   Total: {added + updated} stations processed")
    print("=" * 60)
    
    # Show some sample stations
    print("\n📋 Sample imported stations from Colorado:")
    sample = station_repo.get_stations_by_state('CO')
    if sample is not None and not sample.empty:
        for _, station in sample.head(3).iterrows():
            print(f"   {station['site_id']}: {station['station_name']}, {station['state']}")
    
    print("\n📋 Total stations in database by state:")
    for state in ['UT', 'AZ', 'CO']:
        count = len(station_repo.get_stations_by_state(state))
        print(f"   {state}: {count} stations")
    
    return True


if __name__ == '__main__':
    import_southwest_stations()
