# USGS Streamflow Dashboard - Pacific Northwest

A real-time interactive web dashboard for visualizing and analyzing USGS streamflow data across the Pacific Northwest region. Built with Python Dash and featuring an integrated mapping system with watershed boundary visualization.

![USGS Streamflow Dashboard](https://img.shields.io/badge/status-production-green)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-public_domain-lightgrey)

## Overview

This dashboard provides real-time access to discharge data from 1,500+ USGS monitoring stations across Washington, Oregon, Idaho, Montana, Nevada, and California. It features an interactive map with watershed boundaries, configurable data collection schedules, and comprehensive administrative tools.

## Key Features

### 🗺️ **Interactive Mapping**
- Real-time station locations with color-coded status indicators
- Watershed boundary visualization with hierarchical HUC layers:
  - HUC2: Major basins (Columbia River Basin)
  - HUC4: Sub-regions (e.g., Upper Columbia, Snake River)
  - HUC6: Accounting units (e.g., Kootenai, Pend Oreille, Spokane)
  - HUC8: Cataloging units (detailed watersheds)
- Station filtering by state, basin, and activity status
- Mapbox integration with terrain and satellite views

### � **Data Visualization**
- Real-time discharge graphs with 7-day history
- Daily discharge trends and statistics
- Water year analysis (October 1 - September 30)
- Comparative analysis across multiple years
- Interactive Plotly charts with zoom and pan

### 🔄 **Automated Data Collection**
- Configurable collection schedules for real-time and daily data
- Batch processing with error handling and retry logic
- Database-driven configuration management
- Smart scheduling with interval-based updates
- Collection monitoring and activity logs

### �️ **Administrative Interface**
- Station management and metadata editing
- Configuration management for station groups
- Schedule creation and monitoring
- System health monitoring and diagnostics
- Collection job history and error tracking
- User authentication and access control

## Quick Start

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/geoskimoto/usgs-streamflow-dashboard.git
cd usgs-streamflow-dashboard
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

### Required Dependencies
- `dash` - Web framework
- `plotly` - Interactive visualizations
- `pandas` - Data manipulation
- `dataretrieval` - USGS data access
- `sqlite3` - Database (built-in)
- `gunicorn` - Production server

### Basic Setup

3. **Initialize the database:**
```bash
python initialize_database.py --db-path data/usgs_data.db
```

4. **Import station metadata:**
```bash
python import_stations.py
```

5. **Collect initial data (optional):**
```bash
# Collect real-time data (last 7 days)
python update_realtime_discharge_configurable.py

# Collect daily data (full water years)
python update_daily_discharge_configurable.py
```

6. **Start the dashboard:**
```bash
# Development mode
python app.py

# Production mode
gunicorn --bind 0.0.0.0:8050 --workers 1 --timeout 120 app:server
```

7. **Access the dashboard:**
   - Open http://localhost:8050 in your web browser
   - Admin panel available at the 🔧 Admin tab

## Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for comprehensive deployment instructions including:
- Watershed boundary data setup
- Platform-specific configurations (Render, Heroku, Docker)
- Automated data collection setup
- Environment variables and optimization
- Troubleshooting guide

**Quick deployment checklist:**
- ✅ Python dependencies installed
- ✅ HUC boundary files in `data/basemaps/`
- ✅ Station CSV files in root directory  
- ✅ Database initialized with `initialize_database.py`
- ✅ Stations imported with `import_stations.py`
- ✅ Initial data collected (optional but recommended)

## Project Structure

```
📁 usgs-streamflow-dashboard/
├── 📄 app.py                              # Main Dash application
├── 📄 initialize_database.py              # Database setup script
├── 📄 import_stations.py                  # Station import script
├── 📄 update_realtime_discharge_configurable.py  # Real-time collector
├── 📄 update_daily_discharge_configurable.py     # Daily collector
├── 📄 smart_scheduler.py                  # Smart scheduling system
├── 📄 requirements.txt                    # Python dependencies
├── 📄 README.md                          # This file
├── 📄 DEPLOYMENT.md                      # Deployment guide
├── 📄 Procfile                           # Heroku configuration
├── 📄 render.yaml                        # Render.com configuration
├── 📁 usgs_dashboard/                    # Dashboard package
│   ├── 📁 components/                    # UI components
│   │   ├── map_component.py              # Interactive map with HUC boundaries
│   │   ├── graph_component.py            # Discharge graphs
│   │   └── filter_component.py           # Station filters
│   ├── 📁 data/                          # Data management
│   │   ├── data_manager.py               # Database interface
│   │   └── usgs_collector.py             # USGS API interface
│   └── 📁 utils/                         # Utility functions
├── 📁 config/                            # Configuration files
│   ├── default_configurations.json       # Station groups
│   ├── default_schedules.json            # Collection schedules
│   └── system_settings.json              # System settings
├── 📁 data/                              # Data directory
│   ├── usgs_data.db                      # SQLite database
│   └── 📁 basemaps/                      # Watershed boundaries
│       ├── huc2_pnw.geojson              # Major basins
│       ├── huc4_pnw.geojson              # Sub-regions
│       ├── huc6_pnw.geojson              # Accounting units
│       └── huc8_pnw.geojson              # Cataloging units
└── 📁 logs/                              # Application logs
```

## Features in Detail

### Interactive Map

The map component provides:
- **Station markers** color-coded by data availability
- **Watershed boundaries** with 4 hierarchical levels (HUC2/4/6/8)
- **Hover tooltips** showing station name, ID, and metadata
- **Click interaction** to view detailed discharge graphs
- **Filter controls** for state, basin, and status
- **Map styles** including terrain, satellite, and street views

### Data Collection

The system supports flexible data collection:
- **Real-time data**: Instantaneous discharge values (15-minute to hourly)
- **Daily data**: Mean daily discharge values
- **Configurable schedules**: Database-driven collection timing
- **Batch processing**: Efficient multi-station collection
- **Error handling**: Retry logic and error logging
- **Rate limiting**: Respects USGS API guidelines

### Administrative Tools

Admin panel features:
- **Dashboard**: System health, database statistics, recent activity
- **Configurations**: Create and manage station groups
- **Stations**: Browse, filter, and edit station metadata
- **Schedules**: Create and monitor collection jobs
- **Monitoring**: View collection history and errors
- **System Info**: Server details and diagnostics

### Database Schema

The unified database (`usgs_data.db`) includes:
- `stations`: Station metadata and location data
- `realtime_discharge`: Instantaneous discharge values
- `daily_discharge`: Daily mean discharge values
- `configurations`: Station group definitions
- `schedules`: Collection schedule definitions
- `collection_logs`: Data collection history
- Various views for reporting and analysis

## Configuration

### Station Groups

Station groups are defined in `config/default_configurations.json`:

```json
{
  "configurations": [
    {
      "name": "Pacific Northwest Full",
      "description": "All PNW stations",
      "station_selection": {"filter_type": "all"},
      "is_active": true
    }
  ]
}
```

### Collection Schedules

Schedules are defined in `config/default_schedules.json`:

```json
{
  "schedules": [
    {
      "name": "Real-time Every 2 Hours",
      "data_type": "realtime",
      "interval_hours": 2,
      "is_active": true
    }
  ]
}
```

## API and Data Sources

### USGS Water Services

Data is collected from the official USGS Water Services API:
- **Base URL**: https://waterservices.usgs.gov/
- **Services used**:
  - Instantaneous Values (IV): Real-time data
  - Daily Values (DV): Historical daily data
- **Parameter**: 00060 (Discharge, cubic feet per second)

### Watershed Boundary Dataset

Watershed boundaries from the USGS National Watershed Boundary Dataset:
- **Source**: USGS National Hydrography Dataset
- **Format**: GeoJSON (converted from File Geodatabase)
- **Coverage**: Pacific Northwest (HUC region 17)
- **Levels**: HUC2 (1 basin), HUC4 (12 sub-regions), HUC6 (22 accounting units), HUC8 (229 cataloging units)

## Usage Examples

### View Real-time Data

1. Open the dashboard
2. Navigate to a region of interest on the map
3. Click a station marker
4. View the real-time discharge graph (last 7 days)

### Enable Watershed Boundaries

1. Open the sidebar (if closed)
2. Find "Basin Boundaries" section
3. Check the desired HUC levels:
   - Major Basins (HUC2)
   - Sub-regions (HUC4)
   - Accounting Units (HUC6)
   - Cataloging Units (HUC8)
4. Boundaries will appear on the map

### Filter Stations

1. Use the sidebar filters:
   - **State**: Select one or more states
   - **Basin**: Filter by major basin
   - **Status**: Show only active stations
2. Map updates automatically

### Trigger Manual Data Collection

1. Go to Admin panel (🔧 Admin tab)
2. Navigate to Schedules section
3. Click "Run Now" on a schedule
4. Monitor progress in the Monitoring section

## Troubleshooting

### Map Not Loading

- Check browser console for errors
- Verify Mapbox token is configured (if using custom token)
- Ensure `data/basemaps/` directory contains HUC GeoJSON files

### No Stations Visible

- Verify database has stations: `sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM stations;"`
- Run station import: `python import_stations.py`
- Check CSV files exist: `ls -lh *stations*.csv`

### No Data in Graphs

- Collect data: `python update_realtime_discharge_configurable.py`
- Check database: `sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM realtime_discharge;"`
- Verify USGS API connectivity

### Watershed Boundaries Missing

- Ensure files exist: `ls -lh data/basemaps/huc*_pnw.geojson`
- Files should be 71KB to 3.3MB in size
- See DEPLOYMENT.md for obtaining HUC files

## Contributing

Contributions welcome! Areas for enhancement:
- Additional visualization types
- Enhanced statistical analysis
- Multi-site comparison features
- Export functionality (CSV, PDF reports)
- Mobile-responsive design improvements

## License

This project is in the public domain. USGS data is also public domain.

## Acknowledgments

- **USGS Water Services** for providing free access to streamflow data
- **USGS National Hydrography Dataset** for watershed boundaries
- **Plotly/Dash** for the interactive visualization framework
- **Mapbox** for mapping capabilities

## Citation

If you use this dashboard in research or reports, please cite:

> USGS Water Data for the Nation: https://waterdata.usgs.gov/

For the dataretrieval library:

> Hodson, T.O., Hariharan, J.A., Black, S., and Horsburgh, J.S., 2023, dataretrieval (Python): a Python package for discovering and retrieving water data available from U.S. federal hydrologic web services: U.S. Geological Survey software release, https://doi.org/10.5066/P94I5TX3

---

**Questions or Issues?** Check [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting or open an issue on GitHub.
