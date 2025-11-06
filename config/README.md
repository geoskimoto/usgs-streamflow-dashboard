# Configuration Files

This directory contains version-controlled configuration files for the USGS Streamflow Dashboard.

## Overview

The config folder provides default settings that are loaded into the database on first initialization. This allows for:
- **Version control** of default configurations
- **Easy deployment** - configs are included in repository
- **Reproducible setups** - same defaults everywhere
- **No database in git** - runtime data stays local

## Files

### 1. `default_configurations.json`
**Purpose:** Station collection configurations

Defines sets of stations to monitor:
- **Pacific Northwest Full** - All 1,506 stations (default)
- **Columbia River Basin** - 563 stations in HUC17
- **Development Test Set** - 25 stations for testing

**Structure:**
```json
{
  "configurations": [
    {
      "name": "Configuration Name",
      "description": "Human-readable description",
      "is_default": true|false,
      "is_active": true|false,
      "station_source": {
        "type": "csv|filter|manual|database",
        "path": "file.csv",
        "filters": [...]
      }
    }
  ]
}
```

### 2. `default_schedules.json`
**Purpose:** Data collection schedules

Defines when and how to collect data:
- **Hourly Full Update** - Realtime data every hour
- **15-Minute Realtime** - Frequent updates for dev
- **Daily Full Collection** - Complete collection at 2 AM
- **Weekly Metadata Refresh** - Update metadata on Sundays

**Structure:**
```json
{
  "schedules": [
    {
      "name": "Schedule Name",
      "configuration": "Config Name",
      "data_type": "realtime|daily|both",
      "enabled": true|false,
      "timing": {
        "type": "cron|interval",
        "cron_expression": "0 * * * *"
      },
      "options": {
        "retry_on_error": true,
        "max_retries": 3,
        ...
      }
    }
  ]
}
```

### 3. `system_settings.json`
**Purpose:** Application-wide settings

System configuration including:
- Database settings (path, backups, pragmas)
- Data collection options (timeouts, retries, rate limits)
- Dashboard defaults (map style, colors, refresh intervals)
- Admin panel settings (log retention, page size)
- Plotting options (colors, templates, water year)
- Logging configuration (level, format, file rotation)

**Structure:**
```json
{
  "database": { ... },
  "data_collection": { ... },
  "dashboard": { ... },
  "admin_panel": { ... },
  "plotting": { ... },
  "logging": { ... }
}
```

## Loading Priority

Configuration is loaded in this order:

1. **Load config files** → `default_configurations.json`, `default_schedules.json`, `system_settings.json`
2. **Override with environment variables** → `USGS_DB_PATH`, `USGS_LOG_LEVEL`, etc.
3. **Check database exists:**
   - **If NO:** Create database, populate from config files
   - **If YES:** Compare configs:
     - New configs in files → Add to database
     - Existing configs → Keep database version (user may have modified)
     - Changed configs → Log warning, keep database
4. **User modifications via Admin Panel** → Saved to database only (not back to files)

## Environment Variables

You can override settings with environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `USGS_DB_PATH` | Database location | `data/usgs_data.db` |
| `USGS_LOG_LEVEL` | Logging level | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `USGS_DASHBOARD_SECRET_KEY` | Session security | (random string) |
| `USGS_API_TIMEOUT` | API timeout | `30` |
| `USGS_MAX_STATIONS` | Max map stations | `1500` |
| `USGS_BACKUP_ENABLED` | Enable backups | `true`, `false` |

**Example:**
```bash
export USGS_LOG_LEVEL=DEBUG
export USGS_MAX_STATIONS=500
python app.py
```

## Local Overrides

Create `*.local.json` files for local-only settings (gitignored):
- `system_settings.local.json` - Local system overrides
- `custom_config.local.json` - Local-only configurations

Local files are merged with defaults, with local taking precedence.

## Station Source Types

### CSV Source
Load stations from CSV file:
```json
{
  "type": "csv",
  "path": "all_pnw_discharge_stations.csv",
  "id_column": "usgs_id",
  "columns": {
    "usgs_id": "usgs_id",
    "station_name": "station_name",
    ...
  }
}
```

### Filter Source
Derive from existing configuration:
```json
{
  "type": "filter",
  "base_config": "Pacific Northwest Full",
  "filters": [
    {"field": "state", "operator": "in", "value": ["WA", "OR"]},
    {"field": "drainage_area", "operator": ">", "value": 500}
  ],
  "limit": 25
}
```

### Manual Source
Explicit station list:
```json
{
  "type": "manual",
  "station_ids": [
    "12345678",
    "12345679",
    "12345680"
  ]
}
```

### Database Source
Query existing database (for migrations):
```json
{
  "type": "database",
  "query": "SELECT usgs_id FROM stations WHERE state = 'WA'"
}
```

## Filter Operators

Available operators for filter sources:

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `{"field": "state", "operator": "=", "value": "WA"}` |
| `!=` | Not equals | `{"field": "state", "operator": "!=", "value": "CA"}` |
| `>` | Greater than | `{"field": "drainage_area", "operator": ">", "value": 500}` |
| `<` | Less than | `{"field": "drainage_area", "operator": "<", "value": 1000}` |
| `>=` | Greater or equal | `{"field": "years_of_record", "operator": ">=", "value": 10}` |
| `<=` | Less or equal | `{"field": "latitude", "operator": "<=", "value": 49}` |
| `in` | In list | `{"field": "state", "operator": "in", "value": ["WA", "OR", "ID"]}` |
| `not_in` | Not in list | `{"field": "basin", "operator": "not_in", "value": ["Unknown"]}` |
| `contains` | String contains | `{"field": "station_name", "operator": "contains", "value": "RIVER"}` |
| `starts_with` | String starts with | `{"field": "usgs_id", "operator": "starts_with", "value": "12"}` |
| `ends_with` | String ends with | `{"field": "station_name", "operator": "ends_with", "value": "WA"}` |

## Cron Expression Format

Schedules using `type: "cron"` use standard cron format:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6, Sunday = 0)
│ │ │ │ │
* * * * *
```

**Examples:**
- `0 * * * *` - Every hour at minute 0
- `*/15 * * * *` - Every 15 minutes
- `0 0 * * *` - Daily at midnight
- `0 2 * * *` - Daily at 2 AM
- `0 0 * * 0` - Weekly on Sunday at midnight
- `0 3 * * 0` - Weekly on Sunday at 3 AM
- `0 0 1 * *` - Monthly on the 1st at midnight

## Data Types

### realtime
15-minute instantaneous discharge data from USGS IV (instantaneous values) service.

### daily
Historical daily average discharge data from USGS DV (daily values) service.

### both
Collect both realtime and daily data in a single run.

## Modifying Configurations

### Add New Configuration
1. Edit `default_configurations.json`
2. Add new configuration object
3. Run `python initialize_system.py` to update database
4. Or add via Admin Panel (database only)

### Add New Schedule
1. Edit `default_schedules.json`
2. Add new schedule object
3. Run `python initialize_system.py` to update database
4. Or add via Admin Panel (database only)

### Change System Settings
1. Edit `system_settings.json`
2. Restart application
3. Or use environment variables for temporary overrides

## Validation

Config files are validated on load. Common errors:

- **Missing required fields** - Configuration rejected
- **Invalid data types** - Type conversion attempted, then rejected
- **Invalid references** - Configuration referencing non-existent config
- **Invalid cron expressions** - Schedule rejected
- **Invalid filter operators** - Filter ignored
- **Missing CSV files** - Configuration skipped with warning

Check `logs/app.log` for validation errors.

## Examples

See `examples/` directory for additional configuration examples:
- `examples/custom_configuration.json` - Custom config example
- `examples/custom_schedule.json` - Custom schedule example
- `examples/development_config.json` - Development setup
- `examples/production_config.json` - Production setup

## Best Practices

1. **Keep defaults simple** - Easy to understand and modify
2. **Use descriptive names** - Clear purpose for each config/schedule
3. **Set reasonable limits** - Don't overload the system
4. **Test configurations** - Use dev config for testing
5. **Document changes** - Update descriptions when modifying
6. **Version control** - Commit config changes
7. **Backup before changes** - Easy rollback if needed

## Troubleshooting

### Config not loading
- Check JSON syntax (use validator)
- Check file permissions
- Check logs for validation errors

### Schedule not running
- Verify `enabled: true`
- Check cron expression syntax
- Verify configuration exists
- Check admin panel monitoring tab

### Settings not applied
- Check environment variables override
- Restart application after changes
- Check system_settings.json syntax

### Stations not loading
- Verify CSV file exists
- Check CSV column mappings
- Verify station IDs valid
- Check database populated correctly

## See Also

- `DATABASE_MERGER_PLAN.md` - Overall implementation plan
- `UNIFIED_SCHEMA_DOCS.md` - Database schema documentation
- `QUICK_START.md` - Getting started guide
- `DEPLOY.md` - Deployment instructions
