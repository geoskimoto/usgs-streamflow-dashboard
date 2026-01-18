# Archived Components - DataOps Migration

**Archived Date:** January 17, 2026  
**Reason:** Migration to StreamFlow DataOps API  
**Migration Plan:** See ../INTEGRATION_PLAN.md

---

## Overview

These components were archived during the migration to the StreamFlow DataOps system. The dashboard now uses the DataOps API for all data management operations, with a clean adapter layer providing abstraction and local caching.

**Key Change:** Separation of concerns - data management moved to DataOps, dashboard focuses on visualization.

---

## Archived Components

### 1. Data Collection System

**Location:** `archive/legacy_collectors/`

**Files:**
- `configurable_data_collector.py` (819 lines)
- `update_daily_discharge_configurable.py` (439 lines)
- `update_realtime_discharge_configurable.py` (~400 lines)
- `smart_scheduler.py` (190 lines)
- `setup_scheduling.sh`
- `setup_crontab.sh`

**Total:** ~2,000 lines of code

**Purpose:**
- Fetched USGS discharge data directly from USGS NWIS API
- Managed daily and real-time data collection
- Scheduled data updates via cron jobs
- Stored data in local SQLite database

**Replacement:**
- **DataOps API:** http://localhost:8000/api/v1/
- **Celery tasks:** Automated background data collection
- **Multi-source support:** USGS + Environment Canada + NOAA
- **10,999 stations:** Pre-loaded and maintained

**Why Archived:**
Data collection is now handled centrally by the DataOps system, which provides:
- Better reliability and monitoring
- Multi-source integration
- Centralized configuration
- Automatic retries and error handling

---

### 2. Configuration Management

**Location:** `archive/legacy_config/`

**Files:**
- `json_config_manager.py` (562 lines)
- `default_configurations.json` (117 lines)
- `default_schedules.json` (119 lines)

**Total:** ~800 lines of code

**Purpose:**
- Managed station configurations via JSON files
- Defined data collection schedules
- In-memory caching with TTL
- Station filtering and selection

**Replacement:**
- **DataOps Django Models:** PullConfiguration, Station
- **Web Interface:** http://localhost:8000/streamflow/configurations/
- **Django Admin:** http://localhost:8000/admin/
- **Database-driven:** PostgreSQL/SQLite backend

**Why Archived:**
Configuration is now managed through the DataOps web interface and database, providing:
- Real-time updates without file edits
- Audit trail of changes
- Role-based access control
- Better validation and constraints

---

### 3. Admin Interface

**Location:** `archive/legacy_admin/`

**Files:**
- `admin_components.py` (779 lines)

**Total:** 779 lines of code

**Purpose:**
- Station management (CRUD operations)
- Collection monitoring and logs
- Schedule management
- Configuration editor
- Dashboard settings (mixed with data management)

**Replacement:**
- **DataOps Admin:** http://localhost:8000/streamflow/ (for data management)
- **New Dashboard Admin:** `dashboard_admin.py` (~200 lines, UI settings only)
- **Separation:** Data management vs. visualization settings

**Why Archived:**
Admin interface had mixed concerns. Now split into:
1. **Data management** → DataOps web interface
2. **Dashboard settings** → Minimal dashboard_admin.py (colors, preferences, etc.)

---

### 4. Database Schema

**Location:** `archive/legacy_database/`

**Files:**
- `unified_database_schema.sql` (395 lines)

**Total:** 395 lines of SQL

**Purpose:**
- Custom SQLite schema for dashboard
- 15 tables (stations, streamflow_data, realtime_discharge, configs, logs, etc.)
- Indexes and constraints
- Views for backward compatibility

**Replacement:**
- **DataOps Database:** Django ORM models
- **Dashboard Cache:** Minimal SQLite cache (dataops_cache.db)
- **Adapter Layer:** Handles data format conversion

**Why Archived:**
Dashboard no longer maintains its own data; it queries the DataOps API and caches results locally for performance. The cache schema is much simpler (2 tables vs. 15).

---

## Code Reduction Summary

| Component | Before (LOC) | After | Reduction |
|-----------|--------------|-------|-----------|
| Data Collection | 2,000 | 0 | -2,000 (100%) |
| Configuration | 800 | 0 | -800 (100%) |
| Admin Interface | 779 | ~200 | -579 (74%) |
| Database Schema | 395 | ~50 | -345 (87%) |
| **TOTAL** | **~4,000** | **~250** | **-3,750 (94%)** |

**Net Result:** Dashboard codebase reduced from ~15,000 LOC to ~11,000 LOC (27% reduction)

---

## Rollback Procedure

If the DataOps integration needs to be reverted, follow these steps:

### Quick Rollback (<5 minutes)

```bash
# 1. Disable API mode
cd ~/Proj/streamflow-dashboard/usgs-streamflow-dashboard
sed -i 's/USE_DATAOPS_API=true/USE_DATAOPS_API=false/' .env

# 2. Restore database
cp data/usgs_data.db.backup-* data/usgs_data.db

# 3. Restart dashboard
./scripts/restart_dashboard.sh || python app.py
```

### Full Rollback (if adapter problematic)

```bash
# 1. Revert to pre-migration git tag
git checkout v1.0-pre-dataops-migration

# 2. Or restore files from archive
cp archive/legacy_collectors/* .
cp archive/legacy_admin/admin_components.py .
cp archive/legacy_config/*.py .
cp archive/legacy_config/*.json config/
cp archive/legacy_database/*.sql .

# 3. Restore database
cp data/usgs_data.db.backup-* data/usgs_data.db

# 4. Re-enable cron jobs (if needed)
crontab -e
# Add:
# 0 * * * * cd ~/Proj/streamflow-dashboard/usgs-streamflow-dashboard && python smart_scheduler.py

# 5. Restart
python app.py
```

---

## Migration Timeline

| Date | Action | Status |
|------|--------|--------|
| Jan 17, 2026 | Created integration plan | ✅ Complete |
| Jan 17, 2026 | Phase 0: Preparation & backup | ✅ Complete |
| Jan 17, 2026 | Phase 1: Adapter layer created | ✅ Complete |
| Jan 17, 2026 | Phase 3: Components archived | ✅ Complete |
| TBD | Phase 2: Refactor data_manager.py | ⏳ In Progress |
| TBD | Phase 4: Minimal dashboard admin | ⏳ Pending |
| TBD | Phase 5: Testing & validation | ⏳ Pending |
| TBD | Phase 6: Production deployment | ⏳ Pending |

---

## Key Contacts

| Role | Responsibility |
|------|----------------|
| Dashboard Developer | Visualization components, UI/UX |
| DataOps Developer | API maintenance, data collection |
| DevOps | Deployment, monitoring, rollback |

---

## References

- **Integration Plan:** [../INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md)
- **Architecture Comparison:** [../ARCHITECTURE_COMPARISON.md](../ARCHITECTURE_COMPARISON.md)
- **Analysis Summary:** [../INTEGRATION_ANALYSIS_SUMMARY.md](../INTEGRATION_ANALYSIS_SUMMARY.md)
- **DataOps API Docs:** http://localhost:8000/api/docs/
- **DataOps Dashboard:** http://localhost:8000/streamflow/

---

## Notes for Future Developers

**Q: Can I use the old data collection scripts?**  
A: No, they are archived for reference only. Use the DataOps API instead. If you need custom data collection, add it to the DataOps system.

**Q: How do I add a new station?**  
A: Use the DataOps admin interface: http://localhost:8000/admin/streamflow/station/add/

**Q: How do I change the data collection schedule?**  
A: Edit PullConfiguration in DataOps: http://localhost:8000/streamflow/configurations/

**Q: Where is the data stored now?**  
A: In the DataOps database (PostgreSQL/SQLite). The dashboard caches it locally in `data/dataops_cache.db`.

**Q: What if the API is down?**  
A: The adapter uses hybrid mode by default - it will use the local cache as fallback. Cache is valid for 5 minutes (configurable via `DATAOPS_CACHE_TTL`).

---

**Archive maintained for reference and rollback purposes.**  
**Do not modify archived files - they are frozen in time.**  
**For changes, work with the new DataOps system.**
