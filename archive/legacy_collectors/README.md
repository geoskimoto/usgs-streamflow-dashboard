# Legacy Data Collection Scripts

**Archived:** January 17, 2026  
**Reason:** Replaced by DataOps API

## Files

- `configurable_data_collector.py` - Base collector class (819 LOC)
- `update_daily_discharge_configurable.py` - Daily data updater (439 LOC)
- `update_realtime_discharge_configurable.py` - Real-time data updater (~400 LOC)
- `smart_scheduler.py` - Cron-based scheduler (190 LOC)
- `setup_scheduling.sh` - Scheduler setup script
- `setup_crontab.sh` - Crontab configuration

## Replacement

All data collection is now handled by:
- **DataOps Celery Tasks**: Automated background workers
- **PullConfiguration Models**: Database-driven schedules
- **Multi-Source Support**: USGS, Environment Canada, NOAA

## Do Not Use

These scripts are archived for reference only. They will not work with the new adapter-based system.

For data collection configuration, use the DataOps web interface:
http://localhost:8000/streamflow/configurations/
