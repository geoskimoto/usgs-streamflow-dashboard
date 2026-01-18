# Legacy Admin Components

**Archived:** January 17, 2026  
**Reason:** Separation of concerns - data management moved to DataOps

## Files

- `admin_components.py` - Full admin interface (779 LOC)
  - Station management CRUD
  - Collection monitoring
  - Schedule management  
  - Configuration editor
  - Dashboard settings

## Replacement

**For Data Management:**
- DataOps Web Interface: http://localhost:8000/streamflow/
- Django Admin: http://localhost:8000/admin/

**For Dashboard Settings:**
- New minimal `dashboard_admin.py` (~200 LOC)
- Only UI preferences, themes, display settings

## Why Archived

The old admin mixed two concerns:
1. Data management (stations, schedules, collection) ← Now in DataOps
2. Dashboard settings (colors, preferences) ← Stays in dashboard

Clean separation improves maintainability.
