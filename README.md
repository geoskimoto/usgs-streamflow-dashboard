# USGS Streamflow Dashboard

A modern, interactive dashboard for visualizing and analyzing USGS streamflow data across the Pacific Northwest.

## Documentation

See the [`Documentation/`](./Documentation/) folder for:
- `README.md` - Full project documentation
- `ARCHITECTURE.md` - System architecture and design decisions
- `DATABASE_SCHEMA.md` - Database structure and relationships
- `DEPLOYMENT.md` - Deployment instructions
- `QUICK_START.md` - Quick start guide

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Initialize the database:
   ```bash
   python -m usgs_dashboard.data.database.schema_manager
   ```

3. Run the dashboard:
   ```bash
   python app.py
   ```

## Project Structure

```
usgs-streamflow-dashboard/
├── app.py                          # Main Dash application
├── usgs_dashboard/                 # Core application package
│   ├── data/                       # Data access layer
│   │   ├── database/               # Repository pattern (NEW)
│   │   └── data_manager.py        # Data retrieval & caching
│   ├── components/                 # Dashboard components
│   │   └── viz_manager.py         # Visualization management
│   └── utils/                      # Utility functions
│       ├── water_year_calculator.py # Water year calculations
│       └── water_year_datetime.py   # Water year utilities
├── configurable_data_collector.py  # Data collection framework
├── smart_scheduler.py              # Collection scheduling
├── admin_components.py             # Admin UI components
├── streamflow_analyzer.py          # Standalone analysis tool
├── Documentation/                  # Project documentation
├── scripts/                        # Utility scripts
│   ├── data_prep/                 # Data preparation scripts
│   └── legacy/                    # Archived/superseded scripts
├── config/                        # Configuration files
├── data/                          # Database and data files
├── tests/                         # Test suite
└── Archive/                       # Historical code and docs
```

## Recent Improvements

### Visualization Refactoring
- Consolidated all plotting in `viz_manager.py`
- Created `water_year_calculator.py` as single source of truth
- Eliminated ~377 lines of duplicate code

### Database Refactoring
- Implemented Repository pattern for clean database access
- Created modular database layer in `usgs_dashboard/data/database/`
- Removed raw SQL from application code
- Improved testability and maintainability

## License

MIT License - See LICENSE file for details
