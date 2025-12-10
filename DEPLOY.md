# 🚀 Deployment Guide

## TL;DR - Quick Deployment

```bash
# Fresh deployment (first time)
pip install -r requirements.txt
python deploy.py

# Subsequent starts
python deploy.py --quick
```

That's it! Open http://localhost:8050 when it says "Dash is running on..."

---

## Deployment Options

### Full Deployment (Fresh Server)
```bash
python deploy.py
```
**Does:**
- ✅ Checks dependencies
- ✅ Initializes database schema
- ✅ Imports 4,480+ stations (PNW, Columbia Basin, Southwest)
- ✅ Pre-populates real-time data (~5-10 min)
- ✅ Starts dashboard

**Time:** ~10-15 minutes first run

---

### Fast Deployment (Skip Data Pre-population)
```bash
python deploy.py --skip-data
```
**Does:** Same as above but skips data pre-population  
**Time:** ~2-3 minutes  
**Note:** Data fetched on-demand when you click stations

---

### Setup Only (No Dashboard Start)
```bash
python deploy.py --setup-only
```
**Does:** Database + stations only, doesn't start dashboard  
**Use:** When you want to run dashboard separately or on different port

---

### Quick Start (Already Set Up)
```bash
python deploy.py --quick
```
**Does:** Just starts the dashboard  
**Use:** When database and stations already exist  
**Time:** <5 seconds

---

## What Gets Deployed

### Stations (4,480+ total)
- **PNW HADS**: 1,506 stations (WA, OR, ID, MT, CA, NV)
- **Columbia Basin**: 563 stations (Columbia River watershed)
- **Southwest**: 2,974 stations (UT, AZ, CO)

### Database
- Location: `data/usgs_data.db`
- Schema: Unified schema with stations, discharge data, logs
- Size: ~6 MB (empty), ~50-100 MB (with data)

### Optional Data Pre-population
- Real-time discharge: Last 7 days, 15-minute intervals
- Daily discharge: Full water years (optional, run separately)

---

## Manual Deployment (If You Prefer)

If you want to run steps individually:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database
python -m usgs_dashboard.data.database.schema_manager

# 3. Import stations
python scripts/data_prep/import_all_stations.py

# 4. (Optional) Pre-populate data
python update_realtime_discharge_configurable.py
python update_daily_discharge_configurable.py

# 5. Start dashboard
python app.py
```

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "CHECK constraint failed: source_dataset"
You're on an old schema version. Update and redeploy:
```bash
git pull
rm data/usgs_data.db
python deploy.py
```

### "RuntimeWarning" when running schema_manager
This is harmless - Python module execution warning. Ignore it.

### Stations show "No streamflow data available"
Expected for ~80% of Southwest stations. They exist but don't have active discharge monitoring.

### Port 8050 already in use
```bash
# Kill existing process
lsof -ti:8050 | xargs kill -9

# Or run on different port
# Edit app.py line with app.run_server(port=8050) to different port
```

### Database locked error
Another process is using the database. Stop all Python processes:
```bash
pkill -f "python.*app.py"
```

---

## Production Deployment (Render, Heroku, etc.)

### Render.com

The `render.yaml` is configured for automatic deployment:

```yaml
services:
  - type: web
    name: usgs-streamflow-dashboard
    env: python
    buildCommand: pip install -r requirements.txt && python deploy.py --setup-only --skip-data
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

**Important:** Add persistent disk for database or it will reset on each deploy.

### Heroku

Use `Procfile`:
```
web: python deploy.py --setup-only --skip-data && gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN python deploy.py --setup-only --skip-data

CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "1", "--timeout", "120", "app:server"]
```

---

## Environment Variables

```bash
# Optional configuration
export PORT=8050                    # Dashboard port
export DB_PATH=data/usgs_data.db   # Database location
export DASH_DEBUG=false            # Debug mode (development only)
```

---

## Data Collection (Optional)

Schedule automated data updates:

```bash
# Add to crontab
crontab -e

# Real-time updates every 2 hours
0 */2 * * * cd /path/to/dashboard && python update_realtime_discharge_configurable.py

# Daily updates twice per day
0 6,18 * * * cd /path/to/dashboard && python update_daily_discharge_configurable.py
```

Or use the smart scheduler:
```bash
python smart_scheduler.py
```

---

## Monitoring

Check logs:
```bash
# Application logs
tail -f logs/*.log

# Collection logs (if scheduled)
tail -f logs/realtime_updates.log
tail -f logs/daily_updates.log
```

Check database status:
```bash
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM stations;"
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM realtime_discharge;"
```

---

## Updating

Pull latest changes and redeploy:

```bash
git pull
python deploy.py --skip-data
```

Stations and database schema updates will be applied automatically.

---

## Getting Help

1. Check troubleshooting section above
2. Review `Documentation/` folder for detailed docs
3. Check USGS data service status: https://waterservices.usgs.gov/
4. Open GitHub issue with error details

---

## Summary

**For most deployments, just run:**
```bash
pip install -r requirements.txt
python deploy.py
```

**Done!** 🎉
