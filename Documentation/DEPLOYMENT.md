# USGS Streamflow Dashboard - Deployment Guide

## Overview

This guide covers deploying the USGS Streamflow Dashboard with all required data sources:
- Station database with metadata
- Real-time and daily discharge data
- Watershed boundary (HUC) layers for map visualization

## Prerequisites

### System Requirements
- Python 3.11 or higher
- GDAL/OGR tools (for HUC boundary processing)
- 5+ GB disk space (for database and HUC boundaries)
- Internet connection (for USGS data collection)

### Required Files

The following files must be present for full functionality:

**Station Data:**
- `pnw_usgs_discharge_stations_hads.csv` - PNW HADS stations (root directory)
- `columbia_basin_hads_stations.csv` - Columbia Basin stations (root directory)

**Watershed Boundaries:**
- `data/basemaps/huc2_pnw.geojson` - Major basins (HUC2)
- `data/basemaps/huc4_pnw.geojson` - Sub-regions (HUC4)
- `data/basemaps/huc6_pnw.geojson` - Accounting units (HUC6)
- `data/basemaps/huc8_pnw.geojson` - Cataloging units (HUC8)

**Database:**
- `data/usgs_data.db` - Main SQLite database (auto-created)

**Configuration Files:**
- `config/default_configurations.json` - Station group configurations
- `config/default_schedules.json` - Data collection schedules
- `config/system_settings.json` - System settings

## Deployment Steps

### Step 1: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install GDAL (if processing HUC boundaries from scratch)
# Ubuntu/Debian:
sudo apt-get install gdal-bin python3-gdal

# macOS:
brew install gdal
```

### Step 2: Prepare Watershed Boundary Data

You have two options:

#### Option A: Use Existing HUC Files (Recommended)

If you have the pre-processed HUC GeoJSON files:

```bash
# Ensure data/basemaps directory exists
mkdir -p data/basemaps

# Copy the HUC files to data/basemaps/
# Files needed:
# - huc2_pnw.geojson (71 KB)
# - huc4_pnw.geojson (519 KB)
# - huc6_pnw.geojson (848 KB)
# - huc8_pnw.geojson (3.3 MB)
```

#### Option B: Generate HUC Files from National Geodatabase

If you need to generate the HUC files:

```bash
# 1. Download USGS Watershed Boundary Dataset
cd data/basemaps
wget https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/National/GDB/WBD_National_GDB.zip

# 2. Extract HUC layers from geodatabase
cd ../..
python extract_watershed_boundaries.py

# 3. Create Pacific Northwest regional subsets
python create_regional_subsets.py

# This creates:
# - data/basemaps/huc2_pnw.geojson (1 basin)
# - data/basemaps/huc4_pnw.geojson (12 sub-regions)
# - data/basemaps/huc6_pnw.geojson (22 accounting units)
# - data/basemaps/huc8_pnw.geojson (229 cataloging units)
```

### Step 3: Initialize Database

```bash
# Create database schema and initialize empty database
python initialize_database.py --db-path data/usgs_data.db
```

This creates the unified database with all required tables but no data yet.

### Step 4: Import Station Metadata

```bash
# Import stations from CSV files
python import_stations.py

# This imports:
# - 1,506 stations from pnw_usgs_discharge_stations_hads.csv
# - Additional stations from columbia_basin_hads_stations.csv
```

Verify the import:
```bash
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM stations;"
# Should show ~1,506 stations
```

### Step 5: Collect Initial Data

You have two options for populating discharge data:

#### Option A: Use Configuration-Based Collector (Recommended)

```bash
# Collect real-time data (last 7 days) for active stations
python update_realtime_discharge_configurable.py

# Collect daily data (full water years) for active stations
python update_daily_discharge_configurable.py
```

These scripts use the configuration database to determine which stations to collect.

#### Option B: Manual Test Collection

```bash
# Test with a single station
python -c "
from usgs_dashboard.data.data_manager import USGSDataManager
dm = USGSDataManager()
# Collect data for a test station (e.g., Columbia River at The Dalles)
dm.update_realtime_discharge('14105700')
print('Real-time data collected successfully!')
"
```

### Step 6: Verify Data Collection

Check that data was collected:

```bash
# Check real-time data count
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM realtime_discharge;"

# Check daily data count
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM daily_discharge;"

# List stations with data
sqlite3 data/usgs_data.db "
SELECT s.site_id, s.station_name, COUNT(r.id) as rt_records
FROM stations s
LEFT JOIN realtime_discharge r ON s.site_id = r.site_id
GROUP BY s.site_id
HAVING rt_records > 0
LIMIT 10;
"
```

### Step 7: Start Dashboard

```bash
# Development mode
python app.py

# Production mode with gunicorn
gunicorn --bind 0.0.0.0:8050 --workers 1 --timeout 120 app:server
```

Dashboard will be available at: http://localhost:8050

### Step 8: Set Up Automated Data Collection (Optional)

For production deployments, set up scheduled data collection:

```bash
# Run the setup script
bash setup_scheduling.sh

# This configures cron jobs for:
# - Real-time updates every 2 hours
# - Daily updates at 6 AM and 6 PM
```

Or manually add to crontab:
```bash
crontab -e

# Add these lines:
# Real-time updates every 2 hours
0 */2 * * * cd /path/to/dashboard && python3 update_realtime_discharge_configurable.py >> logs/realtime_updates.log 2>&1

# Daily updates twice per day
0 6,18 * * * cd /path/to/dashboard && python3 update_daily_discharge_configurable.py >> logs/daily_updates.log 2>&1
```

## Platform-Specific Deployment

### Render.com

The included `render.yaml` is configured for Render deployment:

```yaml
services:
  - type: web
    name: usgs-streamflow-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python initialize_database.py --db-path data/usgs_data.db && gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

**Important for Render:**
1. The HUC boundary files must be included in your repository
2. Database will be ephemeral unless you use Render Disks
3. Consider adding a persistent disk mount at `/data` for the database
4. Station CSV files should be committed to the repository

### Heroku

Use the included `Procfile`:

```
web: python initialize_database.py --db-path data/usgs_data.db && gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

**Important for Heroku:**
1. Commit HUC boundary files to repository
2. Database is ephemeral - use Heroku Postgres addon if persistence needed
3. Consider using buildpack for GDAL if processing HUC files

### Docker (Future)

For containerized deployment, ensure your Dockerfile:
1. Installs GDAL if processing HUC boundaries
2. Copies all HUC GeoJSON files to `data/basemaps/`
3. Copies station CSV files to root directory
4. Runs `initialize_database.py` during container startup
5. Optionally runs `import_stations.py` during startup

## Verification Checklist

After deployment, verify all features work:

- [ ] Dashboard loads at the correct URL
- [ ] Map displays with stations visible
- [ ] Watershed boundaries toggle on/off correctly:
  - [ ] HUC2 (Major Basins) - 1 basin
  - [ ] HUC4 (Sub-regions) - 12 sub-regions
  - [ ] HUC6 (Accounting Units) - 22 accounting units
  - [ ] HUC8 (Cataloging Units) - 229 cataloging units
- [ ] Station filters work (state, basin, etc.)
- [ ] Clicking a station shows discharge data/graph
- [ ] Real-time data displays if collected
- [ ] Daily data displays if collected
- [ ] Admin panel accessible (if using authentication)

## File Size Reference

**HUC Boundary Files:**
- `huc2_pnw.geojson` - 71 KB (1 feature)
- `huc4_pnw.geojson` - 519 KB (12 features)
- `huc6_pnw.geojson` - 848 KB (22 features)
- `huc8_pnw.geojson` - 3.3 MB (229 features)

**Station CSV Files:**
- `pnw_usgs_discharge_stations_hads.csv` - ~200 KB
- `columbia_basin_hads_stations.csv` - ~100 KB

**Database:**
- Empty: ~200 KB
- With stations only: ~500 KB
- With 7 days real-time data: 5-10 MB
- With full daily data (10 years): 50-100 MB

## Troubleshooting

### HUC Boundaries Not Showing

**Symptom:** Map loads but watershed boundaries don't appear

**Solutions:**
1. Check files exist:
   ```bash
   ls -lh data/basemaps/huc*_pnw.geojson
   ```

2. Verify file contents:
   ```bash
   head -n 5 data/basemaps/huc2_pnw.geojson
   # Should start with {"type":"FeatureCollection"
   ```

3. Check browser console for JavaScript errors

4. Verify map component loads boundaries:
   ```bash
   grep -n "add_watershed_boundaries" app.py
   ```

### No Stations Appearing

**Symptom:** Empty map with no station markers

**Solutions:**
1. Check database has stations:
   ```bash
   sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM stations;"
   ```

2. Run station import:
   ```bash
   python import_stations.py
   ```

3. Verify CSV files exist:
   ```bash
   ls -lh *stations*.csv
   ```

### No Discharge Data

**Symptom:** Stations visible but no graphs/data when clicked

**Solutions:**
1. Check if data exists in database:
   ```bash
   sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM realtime_discharge;"
   sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM daily_discharge;"
   ```

2. Manually collect data:
   ```bash
   python update_realtime_discharge_configurable.py
   python update_daily_discharge_configurable.py
   ```

3. Check USGS API connectivity:
   ```bash
   curl "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=14105700&parameterCd=00060&siteStatus=all"
   ```

### Database Errors

**Symptom:** SQLite errors or missing tables

**Solutions:**
1. Check database schema:
   ```bash
   sqlite3 data/usgs_data.db ".schema stations"
   ```

2. Reinitialize database:
   ```bash
   rm data/usgs_data.db
   python initialize_database.py --db-path data/usgs_data.db
   python import_stations.py
   ```

## Environment Variables

Configure these for production:

```bash
# Dashboard settings
export PORT=8050                    # Port to run on
export DASH_DEBUG=false             # Disable debug mode in production

# Database settings  
export DB_PATH=data/usgs_data.db    # Path to SQLite database

# Data collection settings
export COLLECTION_BATCH_SIZE=50     # Number of stations per batch
export COLLECTION_DELAY=1           # Delay between requests (seconds)
```

## Performance Optimization

For large deployments:

1. **Database Indexing:** Indexes are created automatically by `unified_database_schema.sql`

2. **Map Performance:** HUC files are already simplified for web performance

3. **Data Collection:** Use batch processing and delays to avoid rate limiting

4. **Caching:** Consider adding Redis for caching map tiles and station data

## Maintenance

### Regular Tasks

**Daily:**
- Monitor data collection logs
- Check for failed collection jobs

**Weekly:**
- Review database size and clean old data if needed
- Check for stations with missing data

**Monthly:**
- Update station metadata from USGS
- Review and optimize database indexes
- Backup database

### Database Maintenance

```bash
# Vacuum database to reclaim space
sqlite3 data/usgs_data.db "VACUUM;"

# Check database integrity
sqlite3 data/usgs_data.db "PRAGMA integrity_check;"

# Backup database
cp data/usgs_data.db data/usgs_data_backup_$(date +%Y%m%d).db
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in `logs/` directory
3. Check USGS data service status: https://waterservices.usgs.gov/
4. Open an issue on GitHub

## Summary

**Minimum files required for deployment:**
1. Python code (all `.py` files)
2. HUC boundary files (4 GeoJSON files in `data/basemaps/`)
3. Station CSV files (2 files in root directory)
4. Configuration files (3 JSON files in `config/`)
5. Database schema SQL file

**Data that auto-generates:**
1. `data/usgs_data.db` - Created by `initialize_database.py`
2. Discharge data - Collected by update scripts
3. Log files - Created by scheduled jobs

**Time to deploy:**
- Fresh setup: 15-30 minutes
- With existing HUC files: 5-10 minutes
- Database initialization: 1-2 minutes
- Station import: 1-2 minutes
- Initial data collection: 30-60 minutes (varies by station count)
