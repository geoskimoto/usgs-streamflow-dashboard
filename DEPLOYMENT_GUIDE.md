# Deployment Guide

## Database Initialization

The application now includes an automatic database initialization script that runs on deployment.

### What Happens on First Deployment

1. **Database Creation**: The `initialize_database.py` script automatically creates `usgs_data.db` with the complete schema
2. **Empty Database**: The database starts empty - no stations or data
3. **App Startup**: The Dash application starts normally

### Populating the Database

After deployment, you need to populate the database with station data:

1. **Review Configurations**: Check `config/default_configurations.json` for available station sets
2. **Run Data Collection**: Execute the data collector to load stations and data
3. **Monitor Progress**: Check the Admin panel for collection logs

### Manual Database Initialization

If you need to initialize the database manually:

```bash
python initialize_database.py
```

This script is idempotent - safe to run multiple times. If the database already exists, it will skip creation.

## Deployment Platforms

### Render.com

The `render.yaml` file is configured to automatically run database initialization on deployment:

```yaml
startCommand: python initialize_database.py && gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

### Heroku / Other Platforms

The `Procfile` includes the same initialization:

```
web: python initialize_database.py && gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

## Database Schema

The unified `usgs_data.db` includes these tables:

- **stations**: Station metadata (location, name, etc.)
- **configurations**: Configuration management
- **schedules**: Data collection schedules
- **collection_logs**: Collection history and status
- **station_errors**: Error tracking
- **streamflow_data**: Daily discharge values
- **realtime_discharge**: 15-minute discharge values

## Troubleshooting

### Database Not Found Error

If you see "Configuration database not found" errors:

1. Check that `usgs_data.db` exists in the application root
2. Run `python initialize_database.py` manually
3. Check file permissions

### Empty Dashboard

If the dashboard shows no stations:

1. The database exists but is empty - this is normal on first deployment
2. Run data collection: `python configurable_data_collector.py`
3. Or use the Admin panel to trigger manual collection

### Database Schema Issues

If you need to recreate the database:

```bash
rm usgs_data.db
python initialize_database.py
```

## Next Steps After Deployment

1. ✅ Database automatically initialized
2. 📋 Review configuration files in `config/` folder
3. 🚀 Run data collection to populate stations
4. 📊 Start using the dashboard
5. ⚙️ Configure schedules in the Admin panel
