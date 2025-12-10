# Data Preparation Scripts

Scripts for fetching, validating, and importing USGS streamflow station data.

## Quick Start - Fresh Deployment

For a fresh deployment, run these commands in order:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database schema (optional - import script will do this automatically)
python -m usgs_dashboard.data.database.schema_manager

# 3. Import all stations (PNW, Columbia Basin, Southwest)
python scripts/data_prep/import_all_stations.py

# 4. Start the dashboard
python app.py
```

That's it! The dashboard will fetch data on-demand when you click stations.

## Import Scripts

### `import_all_stations.py` - **RECOMMENDED**

Unified script that imports all station datasets into the database.

**Import all datasets:**
```bash
python scripts/data_prep/import_all_stations.py
```

**Import specific datasets:**
```bash
# Only PNW HADS stations
python scripts/data_prep/import_all_stations.py --pnw-only

# Only Columbia Basin HADS stations  
python scripts/data_prep/import_all_stations.py --columbia-only

# Only Southwest states (UT, AZ, CO)
python scripts/data_prep/import_all_stations.py --southwest-only

# Custom database path
python scripts/data_prep/import_all_stations.py --db-path /path/to/usgs_data.db
```

**What it imports:**
- **PNW HADS**: 1,506 stations (WA, OR, ID, MT, CA, NV)
- **Columbia Basin**: 563 stations (Columbia River watershed)
- **Southwest**: 2,974 stations (UT, AZ, CO)
- **Total**: 4,480+ stations

## Data Fetching Scripts

### `fetch_southwest_discharge_stations.py`

Fetches station metadata from USGS API for Southwest states.

```bash
python scripts/data_prep/fetch_southwest_discharge_stations.py
```

**Output:**
- `data/southwest_discharge_stations.csv` - All stations found
- `data/southwest_stations_summary.txt` - Summary statistics

**Note:** This has already been run. The CSV is in the repository.

## Validation Scripts

### `validate_southwest_stations.py`

Tests which Southwest stations actually have discharge data available.

```bash
# Test sample (default: 20 stations per state)
python scripts/data_prep/validate_southwest_stations.py

# Test custom sample size
python scripts/data_prep/validate_southwest_stations.py --sample 30

# Test ALL stations (takes 1-2 hours)
python scripts/data_prep/validate_southwest_stations.py --full
```

**Output:**
- `data/southwest_discharge_stations_validated.csv` - Stations with data
- `data/southwest_discharge_stations_validated_invalid.csv` - Stations without data

**Known Issue:** Only ~20% of Southwest stations have active discharge data:
- Utah: ~30% success rate
- Arizona: ~23% success rate  
- Colorado: ~7% success rate

Invalid stations will show "No streamflow data available" when clicked in the dashboard.

## Legacy Import Scripts

These scripts are superseded by `import_all_stations.py` but kept for reference:

- `import_stations.py` - Old PNW/Columbia import
- `import_stations_clean.py` - Alternative import method
- `import_southwest_stations.py` - Southwest-only import

**Use `import_all_stations.py` instead** - it consolidates all of these.

## Data Collection (Optional)

After importing stations, you can optionally pre-populate discharge data:

```bash
# Collect real-time data (last 7 days)
python update_realtime_discharge_configurable.py

# Collect historical daily data
python update_daily_discharge_configurable.py

# Or collect for specific configuration
python update_daily_discharge_configurable.py --config "Southwest States (UT, AZ, CO)"
```

**Note:** This is optional! The dashboard fetches data on-demand if not pre-populated.

## Station Data Sources

| Dataset | CSV File | Stations | States | Source |
|---------|----------|----------|--------|--------|
| PNW HADS | `data/pnw_usgs_discharge_stations_hads.csv` | 1,506 | WA, OR, ID, MT, CA, NV | USGS HADS |
| Columbia Basin | `data/columbia_basin_hads_stations.csv` | 563 | WA, OR, ID, MT, NV, CA | USGS HADS |
| Southwest | `data/southwest_discharge_stations.csv` | 2,974 | UT, AZ, CO | USGS API |

## Troubleshooting

### "CHECK constraint failed: source_dataset"

**Fixed!** Make sure you're using the latest version of:
- `unified_database_schema.sql` (includes 'Southwest' in allowed values)
- `import_all_stations.py` (uses correct source_dataset values)

### "No streamflow data available"

This is expected for ~80% of Southwest stations. They exist in USGS database but don't have active discharge monitoring. Use `validate_southwest_stations.py` to identify which stations have data.

### RuntimeWarning when running schema_manager

This is a harmless Python warning when executing modules. The script works correctly despite the warning.

### Missing CSV files

Make sure CSV files are in the `data/` directory:
```bash
ls data/*.csv
```

Should show:
- `pnw_usgs_discharge_stations_hads.csv`
- `columbia_basin_hads_stations.csv`
- `southwest_discharge_stations.csv`

## Database Schema

The unified database (`data/usgs_data.db`) uses this schema:

**Core Tables:**
- `stations` - Station metadata (4,480+ stations)
- `streamflow_data` - Historical daily discharge data
- `realtime_discharge` - Real-time (15-min) discharge data

**Operational Tables:**
- `collection_logs` - Data collection execution logs
- `station_errors` - Error tracking per station
- `subset_cache` - Cached filtered station subsets
- `data_statistics` - Cached statistics per station

Schema is defined in `unified_database_schema.sql` in the project root.

## Next Steps After Import

1. ✅ Stations imported
2. ⏩ **Optional:** Pre-populate data with collection scripts
3. ⏩ Start dashboard: `python app.py`
4. ⏩ Open browser to http://localhost:8050
5. ⏩ Click stations on map to view streamflow data

Data will be fetched on-demand from USGS API when you click a station!
