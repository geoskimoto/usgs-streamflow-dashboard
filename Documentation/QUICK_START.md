# Quick Start Guide - USGS Streamflow Dashboard

## ✅ Database Setup Complete!

Your configuration database has been successfully created and populated:

- **Database Location:** `data/station_config.db`
- **Total Stations:** 1,506 active USGS discharge monitoring stations
- **Configurations:** 3 pre-configured station groups
- **Schedules:** 4 automated collection schedules

## 📊 Available Configurations

1. **Pacific Northwest Full** (Default) ⭐
   - 1,506 stations across WA, OR, ID, MT, NV, CA
   - Covers all HADS PNW and Columbia Basin stations

2. **Columbia River Basin (HUC17)**
   - 563 stations in the Columbia River watershed
   - Focused on HUC code 17xx regions

3. **Development Test Set**
   - 25 stations for testing and development
   - Small subset for quick testing

## 🚀 Starting the Dashboard

```bash
python app.py
```

Then open: http://localhost:8050

## 🔧 Accessing Admin Panel

1. Click the **🔧 Admin** tab
2. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`
3. Explore the admin interface:
   - **Dashboard:** System health and overview
   - **Configurations:** Manage station groups
   - **Stations:** Browse and filter stations
   - **Schedules:** Automated collection jobs
   - **Monitoring:** Collection activity and errors

## 🛠️ Database Management Commands

### View configurations:
```bash
sqlite3 data/station_config.db "SELECT * FROM configuration_summary;"
```

### Count stations by state:
```bash
sqlite3 data/station_config.db "SELECT * FROM stations_by_state;"
```

### Check recent activity:
```bash
sqlite3 data/station_config.db "SELECT * FROM recent_collection_activity LIMIT 10;"
```

### Reset database (if needed):
```bash
rm data/station_config.db
python setup_configuration_database.py
python populate_station_database.py
```

## 📝 Next Steps

1. **Start the dashboard** to verify everything works
2. **Login to admin panel** to explore the interface
3. **Review configurations** and adjust as needed
4. **Set up automated schedules** for data collection
5. **Monitor collection logs** to ensure data is updating

## 🔍 Troubleshooting

**Dashboard won't start:**
- Check if another process is using port 8050
- Verify all dependencies are installed: `pip install -r requirements.txt`

**Admin panel shows errors:**
- Verify database exists: `ls -lh data/station_config.db`
- Check database integrity: `sqlite3 data/station_config.db "PRAGMA integrity_check;"`

**No data showing:**
- Initial database is empty - you need to run data collection
- Use admin panel to trigger manual data collection
- Or wait for scheduled collections to run

## 📚 Documentation

- **Full Admin Guide:** `ADMIN_PANEL_DATABASE_GUIDE.md`
- **Admin Interface Summary:** `ADMIN_INTERFACE_SUMMARY.md`
- **Authentication Guide:** `ADMIN_AUTHENTICATION_GUIDE.md`

---

**System Status:** ✅ Ready for production use!
