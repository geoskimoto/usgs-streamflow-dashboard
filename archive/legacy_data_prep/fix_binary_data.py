#!/usr/bin/env python3
"""
Fix binary data in filters table.

Some columns (drainage_area, huc_code) are being stored as binary blobs
instead of proper REAL/TEXT types. This script converts them back.
"""

import sqlite3
import struct

def fix_filters_table():
    """Fix binary columns in filters table."""
    db_path = "data/usgs_cache.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔧 Fixing binary data in filters table...")
    
    # Get all rows
    cursor.execute("SELECT site_id, drainage_area, huc_code FROM filters")
    rows = cursor.fetchall()
    
    fixed_drainage = 0
    fixed_huc = 0
    
    for site_id, drainage_area, huc_code in rows:
        updates = []
        params = []
        
        # Fix drainage_area if it's binary
        if drainage_area is not None and isinstance(drainage_area, bytes):
            try:
                # Try to unpack as double (8 bytes)
                if len(drainage_area) == 8:
                    fixed_value = struct.unpack('d', drainage_area)[0]
                    updates.append("drainage_area = ?")
                    params.append(fixed_value)
                    fixed_drainage += 1
            except:
                # If can't unpack, set to NULL
                updates.append("drainage_area = NULL")
        
        # Fix huc_code if it's binary
        if huc_code is not None and isinstance(huc_code, bytes):
            try:
                # Try to unpack as long (8 bytes) and convert to string
                if len(huc_code) == 8:
                    fixed_value = str(struct.unpack('q', huc_code)[0])
                    updates.append("huc_code = ?")
                    params.append(fixed_value)
                    fixed_huc += 1
            except:
                # If can't unpack, set to NULL
                updates.append("huc_code = NULL")
        
        # Update if needed
        if updates:
            params.append(site_id)
            sql = f"UPDATE filters SET {', '.join(updates)} WHERE site_id = ?"
            cursor.execute(sql, params)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Fixed {fixed_drainage} drainage_area values")
    print(f"✅ Fixed {fixed_huc} huc_code values")
    
    # Verify
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM filters WHERE typeof(drainage_area) = 'blob'")
    blob_drainage = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM filters WHERE typeof(huc_code) = 'blob'")
    blob_huc = cursor.fetchone()[0]
    
    conn.close()
    
    if blob_drainage > 0 or blob_huc > 0:
        print(f"⚠️  Still have binary data:")
        print(f"   drainage_area: {blob_drainage} blobs")
        print(f"   huc_code: {blob_huc} blobs")
    else:
        print(f"✅ All binary data converted successfully!")

if __name__ == '__main__':
    fix_filters_table()
