#!/usr/bin/env python3
"""
Unified Station Import Script

Imports all station types from CSV files into the unified database:
- PNW HADS stations
- Columbia Basin HADS stations  
- Southwest states (UT, AZ, CO) stations

Works with the new repository pattern and usgs_data.db schema.
"""

import sys
from pathlib import Path
import pandas as pd
from typing import List, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from usgs_dashboard.data.database import (
    DatabaseConnection,
    StationRepository,
    SchemaManager
)


class StationImporter:
    """Handles importing stations from various CSV sources into the database."""
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize importer.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        """
        self.db_path = db_path
        self.db_conn = DatabaseConnection(db_path)
        self.schema_mgr = SchemaManager(db_path)
        self.station_repo = StationRepository(db_path)
        
    def ensure_database_initialized(self) -> bool:
        """Ensure database schema is initialized."""
        print("\n📊 Verifying database schema...")
        if not self.schema_mgr.verify_schema():
            print("⚙️  Initializing database schema...")
            # Force initialization if schema is missing
            return self.schema_mgr.initialize_database(force=True)
        print("✓ Database schema verified")
        return True
    
    def import_pnw_hads_stations(self) -> Tuple[int, int]:
        """
        Import PNW HADS stations from CSV.
        
        Returns:
        --------
        Tuple[int, int]
            (added_count, updated_count)
        """
        csv_file = "data/pnw_usgs_discharge_stations_hads.csv"
        source_dataset = "HADS_PNW"
        
        if not Path(csv_file).exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping...")
            return (0, 0)
        
        print(f"\n📂 Loading {csv_file} (source: {source_dataset})")
        df = pd.read_csv(csv_file, dtype={'usgs_id': str})
        print(f"   Found {len(df)} stations in CSV")
        
        # Show state breakdown
        if 'state_code' in df.columns:
            print("   Stations by state:")
            for state, count in df['state_code'].value_counts().items():
                print(f"      {state}: {count}")
        
        # Prepare stations
        stations = []
        for _, row in df.iterrows():
            try:
                station = {
                    'site_id': str(row['usgs_id']).strip().zfill(8),
                    'station_name': str(row['station_name']).strip(),
                    'state': str(row['state_code']).strip(),
                    'latitude': float(row['latitude_decimal']) if pd.notna(row['latitude_decimal']) else None,
                    'longitude': float(row['longitude_decimal']) if pd.notna(row['longitude_decimal']) else None,
                    'huc_code': str(row['huc_cd']).strip() if pd.notna(row.get('huc_cd')) else None,
                    'drainage_area': float(row['drainage_area']) if pd.notna(row.get('drainage_area')) else None,
                    'nws_id': str(row['nws_id']).strip() if pd.notna(row.get('nws_id')) else None,
                    'goes_id': str(row['goes_id']).strip() if pd.notna(row.get('goes_id')) else None,
                    'source_dataset': source_dataset,
                    'is_active': 1
                }
                stations.append(station)
            except Exception as e:
                print(f"   ⚠️  Skipping station {row.get('usgs_id', 'unknown')}: {e}")
                continue
        
        print(f"   Prepared {len(stations)} stations for import")
        
        # Bulk import
        stations_df = pd.DataFrame(stations)
        result = self.station_repo.bulk_upsert_stations(stations_df)
        
        if isinstance(result, tuple):
            added, updated = result
        else:
            added = result
            updated = 0
        
        print(f"   ✅ Processed: {added} added, {updated} updated")
        return (added, updated)
    
    def import_columbia_basin_stations(self) -> Tuple[int, int]:
        """
        Import Columbia Basin HADS stations from CSV.
        
        Returns:
        --------
        Tuple[int, int]
            (added_count, updated_count)
        """
        csv_file = "data/columbia_basin_hads_stations.csv"
        source_dataset = "HADS_Columbia"
        
        if not Path(csv_file).exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping...")
            return (0, 0)
        
        print(f"\n📂 Loading {csv_file} (source: {source_dataset})")
        df = pd.read_csv(csv_file, dtype={'usgs_id': str})
        print(f"   Found {len(df)} stations in CSV")
        
        # Show state breakdown
        if 'state_code' in df.columns:
            print("   Stations by state:")
            for state, count in df['state_code'].value_counts().items():
                print(f"      {state}: {count}")
        
        # Prepare stations
        stations = []
        for _, row in df.iterrows():
            try:
                station = {
                    'site_id': str(row['usgs_id']).strip().zfill(8),
                    'station_name': str(row['station_name']).strip(),
                    'state': str(row['state_code']).strip(),
                    'latitude': float(row['latitude_decimal']) if pd.notna(row['latitude_decimal']) else None,
                    'longitude': float(row['longitude_decimal']) if pd.notna(row['longitude_decimal']) else None,
                    'huc_code': str(row['huc_cd']).strip() if pd.notna(row.get('huc_cd')) else None,
                    'drainage_area': float(row['drainage_area']) if pd.notna(row.get('drainage_area')) else None,
                    'nws_id': str(row['nws_id']).strip() if pd.notna(row.get('nws_id')) else None,
                    'goes_id': str(row['goes_id']).strip() if pd.notna(row.get('goes_id')) else None,
                    'source_dataset': source_dataset,
                    'is_active': 1
                }
                stations.append(station)
            except Exception as e:
                print(f"   ⚠️  Skipping station {row.get('usgs_id', 'unknown')}: {e}")
                continue
        
        print(f"   Prepared {len(stations)} stations for import")
        
        # Bulk import
        stations_df = pd.DataFrame(stations)
        result = self.station_repo.bulk_upsert_stations(stations_df)
        
        if isinstance(result, tuple):
            added, updated = result
        else:
            added = result
            updated = 0
        
        print(f"   ✅ Processed: {added} added, {updated} updated")
        return (added, updated)
    
    def import_southwest_stations(self) -> Tuple[int, int]:
        """
        Import Southwest states (UT, AZ, CO) stations from CSV.
        
        Returns:
        --------
        Tuple[int, int]
            (added_count, updated_count)
        """
        csv_file = "data/southwest_discharge_stations.csv"
        source_dataset = "Southwest"
        
        if not Path(csv_file).exists():
            print(f"⚠️  Warning: {csv_file} not found, skipping...")
            return (0, 0)
        
        print(f"\n📂 Loading {csv_file} (source: {source_dataset})")
        df = pd.read_csv(csv_file, dtype={'site_no': str})
        print(f"   Found {len(df)} stations in CSV")
        
        # Show state breakdown
        if 'state_cd' in df.columns:
            print("   Stations by state:")
            for state, count in df['state_cd'].value_counts().items():
                print(f"      {state}: {count}")
        
        # Prepare stations
        stations = []
        for _, row in df.iterrows():
            try:
                station = {
                    'site_id': str(row['site_no']).strip().zfill(8),
                    'station_name': str(row['station_nm']).strip(),
                    'state': str(row['state_cd']).strip(),
                    'latitude': float(row['latitude']) if pd.notna(row['latitude']) else None,
                    'longitude': float(row['longitude']) if pd.notna(row['longitude']) else None,
                    'huc_code': str(row['huc_code']).strip() if pd.notna(row.get('huc_code')) else None,
                    'drainage_area': float(row['drainage_area']) if pd.notna(row.get('drainage_area')) else None,
                    'source_dataset': source_dataset,
                    'is_active': 1
                }
                stations.append(station)
            except Exception as e:
                print(f"   ⚠️  Skipping station {row.get('site_no', 'unknown')}: {e}")
                continue
        
        print(f"   Prepared {len(stations)} stations for import")
        
        # Bulk import
        stations_df = pd.DataFrame(stations)
        result = self.station_repo.bulk_upsert_stations(stations_df)
        
        if isinstance(result, tuple):
            added, updated = result
        else:
            added = result
            updated = 0
        
        print(f"   ✅ Processed: {added} added, {updated} updated")
        return (added, updated)
    
    def show_summary(self):
        """Display summary of stations in database."""
        print("\n" + "=" * 60)
        print("📊 DATABASE SUMMARY")
        print("=" * 60)
        
        # Total stations
        total_count = self.station_repo.get_station_count()
        print(f"\nTotal stations: {total_count}")
        
        # By state
        print("\nStations by state:")
        states = self.db_conn.execute_query(
            "SELECT state, COUNT(*) as count FROM stations GROUP BY state ORDER BY state",
            fetch='all'
        )
        for state, count in states:
            print(f"   {state}: {count}")
        
        # By source dataset
        print("\nStations by source:")
        sources = self.db_conn.execute_query(
            "SELECT source_dataset, COUNT(*) as count FROM stations GROUP BY source_dataset ORDER BY source_dataset",
            fetch='all'
        )
        for source, count in sources:
            print(f"   {source}: {count}")
        
        print("\n" + "=" * 60)
        print("✅ Import Complete!")
        print("=" * 60)
    
    def run_all_imports(self):
        """Run all station imports."""
        print("🚀 UNIFIED STATION IMPORT")
        print("=" * 60)
        print("Importing all station types into unified database")
        print("=" * 60)
        
        # Ensure database is ready
        if not self.ensure_database_initialized():
            print("❌ Failed to initialize database")
            return False
        
        # Track totals
        total_added = 0
        total_updated = 0
        
        # Import each dataset
        print("\n1️⃣  PNW HADS Stations")
        print("-" * 60)
        added, updated = self.import_pnw_hads_stations()
        total_added += added
        total_updated += updated
        
        print("\n2️⃣  Columbia Basin HADS Stations")
        print("-" * 60)
        added, updated = self.import_columbia_basin_stations()
        total_added += added
        total_updated += updated
        
        print("\n3️⃣  Southwest States (UT, AZ, CO) Stations")
        print("-" * 60)
        added, updated = self.import_southwest_stations()
        total_added += added
        total_updated += updated
        
        # Show summary
        self.show_summary()
        
        print(f"\n📈 Import Statistics:")
        print(f"   New stations added: {total_added}")
        print(f"   Existing stations updated: {total_updated}")
        print(f"   Total processed: {total_added + total_updated}")
        
        print(f"\n📝 Next Steps:")
        print(f"   1. Verify configurations in config/default_configurations.json")
        print(f"   2. Start data collection:")
        print(f"      python update_realtime_discharge_configurable.py")
        print(f"      python update_daily_discharge_configurable.py")
        print(f"   3. Start dashboard: python app.py")
        
        return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import all station types into unified database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import all stations with default database path
  python import_all_stations.py
  
  # Import with custom database path
  python import_all_stations.py --db-path /path/to/usgs_data.db
  
  # Import only specific dataset types
  python import_all_stations.py --pnw-only
  python import_all_stations.py --southwest-only
        """
    )
    
    parser.add_argument(
        '--db-path',
        default='data/usgs_data.db',
        help='Path to database file (default: data/usgs_data.db)'
    )
    
    parser.add_argument(
        '--pnw-only',
        action='store_true',
        help='Import only PNW HADS stations'
    )
    
    parser.add_argument(
        '--columbia-only',
        action='store_true',
        help='Import only Columbia Basin HADS stations'
    )
    
    parser.add_argument(
        '--southwest-only',
        action='store_true',
        help='Import only Southwest states (UT, AZ, CO) stations'
    )
    
    args = parser.parse_args()
    
    # Create importer
    importer = StationImporter(args.db_path)
    
    # Ensure database initialized
    if not importer.ensure_database_initialized():
        print("❌ Failed to initialize database")
        sys.exit(1)
    
    # Track totals
    total_added = 0
    total_updated = 0
    
    # Run selected imports
    if args.pnw_only:
        print("🚀 Importing PNW HADS Stations Only")
        print("=" * 60)
        added, updated = importer.import_pnw_hads_stations()
        total_added += added
        total_updated += updated
    elif args.columbia_only:
        print("🚀 Importing Columbia Basin HADS Stations Only")
        print("=" * 60)
        added, updated = importer.import_columbia_basin_stations()
        total_added += added
        total_updated += updated
    elif args.southwest_only:
        print("🚀 Importing Southwest States Stations Only")
        print("=" * 60)
        added, updated = importer.import_southwest_stations()
        total_added += added
        total_updated += updated
    else:
        # Import all
        success = importer.run_all_imports()
        if not success:
            sys.exit(1)
        return
    
    # Show summary for single-dataset imports
    importer.show_summary()
    print(f"\n📈 Import Statistics:")
    print(f"   New stations added: {total_added}")
    print(f"   Existing stations updated: {total_updated}")
    print(f"   Total processed: {total_added + total_updated}")


if __name__ == '__main__':
    main()
