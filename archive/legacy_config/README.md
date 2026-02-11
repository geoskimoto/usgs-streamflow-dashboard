# Legacy Configuration Management

**Archived:** January 17, 2026  
**Reason:** Replaced by DataOps database-driven configuration

## Files

- `json_config_manager.py` - JSON config manager with caching (562 LOC)
- `default_configurations.json` - Station configurations (117 LOC)
- `default_schedules.json` - Collection schedules (119 LOC)

## Replacement

**DataOps PullConfiguration Models:**
- Database-driven configuration
- Real-time updates without file edits
- Web interface for editing
- Audit trail of changes

**Access:**
- Configurations: http://localhost:8000/streamflow/configurations/
- Django Admin: http://localhost:8000/admin/streamflow/pullconfiguration/

## Why Archived

JSON file-based configuration had limitations:
- Required code restart for changes
- No audit trail
- File locking issues
- No role-based access control

Database-driven config in DataOps provides better management and scalability.
