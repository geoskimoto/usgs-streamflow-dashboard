# Legacy Database Schema

**Archived:** January 17, 2026  
**Reason:** Dashboard no longer maintains full data database

## Files

- `unified_database_schema.sql` - Complete SQLite schema (395 LOC)
  - 15 tables
  - Indexes and constraints
  - Views for compatibility

## Original Tables

1. `stations` - Station metadata
2. `streamflow_data` - Daily historical data (JSON blobs)
3. `realtime_discharge` - 15-minute real-time data
4. `station_lists` - Configuration-based station groups
5. `configurations` - Station configurations
6. `schedules` - Collection schedules
7. `collection_logs` - Collection execution logs
8. `collection_progress` - Real-time progress tracking
9-15. Various indexes and metadata tables

## Replacement

**DataOps Database:**
- Django ORM models
- PostgreSQL/SQLite backend
- RESTful API access

**Dashboard Cache:**
- Minimal SQLite cache (`dataops_cache.db`)
- Only 2 tables:
  - `cache_stations`
  - `cache_discharge`
- 5-minute TTL (configurable)

## Why Archived

Dashboard no longer needs to maintain its own data warehouse. Benefits:
- 87% less database code
- Simpler maintenance
- Single source of truth (DataOps)
- API provides data on demand
- Local cache for performance

For data queries, use: `dataops_adapter.DataOpsAdapter()`
