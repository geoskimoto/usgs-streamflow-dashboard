#!/usr/bin/env python3
"""
Sync station metadata from the new configurable system to the dashboard filters table.

This script copies station metadata from station_config.db (station_lists) 
to usgs_cache.db (filters) so the dashboard map and filters work properly.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


def sync_metadata():
    """Sync station metadata from configuration database to cache database."""
    
    config_db = Path('data/station_config.db')
    cache_db = Path('data/usgs_cache.db')
    
    if not config_db.exists():
        print(f"❌ Configuration database not found: {config_db}")
        return False
    
    if not cache_db.exists():
        print(f"❌ Cache database not found: {cache_db}")
        return False
    
    print("🔄 Syncing station metadata from configuration to dashboard...")
    
    # Read from station_lists
    config_conn = sqlite3.connect(config_db)
    config_cursor = config_conn.cursor()
    
    config_cursor.execute("""
        SELECT 
            usgs_id,
            station_name,
            state,
            latitude,
            longitude,
            huc_code,
            drainage_area,
            is_active
        FROM station_lists
        WHERE is_active = 1
        ORDER BY usgs_id
    """)
    
    stations = config_cursor.fetchall()
    config_conn.close()
    
    print(f"📊 Found {len(stations)} active stations in configuration database")
    
    if len(stations) == 0:
        print("⚠️  No stations found to sync")
        return False
    
    # Write to filters table
    cache_conn = sqlite3.connect(cache_db)
    cache_cursor = cache_conn.cursor()
    
    inserted = 0
    updated = 0
    errors = 0
    
    for station in stations:
        usgs_id, station_name, state, lat, lon, huc_code, drainage_area, is_active = station
        
        try:
            # Calculate basin from HUC code (first 4 digits)
            basin = str(huc_code)[:4] if huc_code else None
            
            # Check if station exists in filters
            cache_cursor.execute("SELECT site_id FROM filters WHERE site_id = ?", (usgs_id,))
            exists = cache_cursor.fetchone()
            
            if exists:
                # Update existing record
                cache_cursor.execute("""
                    UPDATE filters SET
                        station_name = ?,
                        latitude = ?,
                        longitude = ?,
                        drainage_area = ?,
                        state = ?,
                        huc_code = ?,
                        basin = ?,
                        is_active = ?,
                        agency = 'USGS',
                        last_updated = ?
                    WHERE site_id = ?
                """, (
                    station_name,
                    lat,
                    lon,
                    drainage_area,
                    state,
                    huc_code,
                    basin,
                    int(is_active),
                    datetime.now().isoformat(),
                    usgs_id
                ))
                updated += 1
            else:
                # Insert new record
                cache_cursor.execute("""
                    INSERT INTO filters (
                        site_id, station_name, latitude, longitude, drainage_area,
                        state, huc_code, basin, is_active, agency,
                        site_type, status, color, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    usgs_id,
                    station_name,
                    lat,
                    lon,
                    drainage_area,
                    state,
                    huc_code,
                    basin,
                    int(is_active),
                    'USGS',
                    'Stream',  # Default type
                    'active' if is_active else 'inactive',
                    '#2E86AB' if is_active else '#999999',  # Blue for active, gray for inactive
                    datetime.now().isoformat()
                ))
                inserted += 1
                
        except Exception as e:
            print(f"❌ Error processing station {usgs_id}: {e}")
            errors += 1
    
    cache_conn.commit()
    cache_conn.close()
    
    print(f"\n✅ Metadata sync complete!")
    print(f"   📥 Inserted: {inserted} new stations")
    print(f"   🔄 Updated: {updated} existing stations")
    if errors > 0:
        print(f"   ❌ Errors: {errors} stations failed")
    
    # Verify the sync
    verify_conn = sqlite3.connect(cache_db)
    verify_cursor = verify_conn.cursor()
    verify_cursor.execute("SELECT COUNT(*) FROM filters")
    total_filters = verify_cursor.fetchone()[0]
    verify_conn.close()
    
    print(f"\n📊 Dashboard filters table now has {total_filters} stations")
    
    return True


if __name__ == '__main__':
    success = sync_metadata()
    exit(0 if success else 1)
