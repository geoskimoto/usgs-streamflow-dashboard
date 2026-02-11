# Architecture Comparison: Current vs. Target

## Current Architecture (Monolithic - Poor Separation of Concerns)

```
┌─────────────────────────────────────────────────────────────────────┐
│                  USGS Streamflow Dashboard                          │
│                     (Monolithic Application)                         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Data Collection Layer (❌ Should be separate)             │   │
│  │  ├── configurable_data_collector.py (819 LOC)              │   │
│  │  ├── update_daily_discharge_configurable.py (439 LOC)      │   │
│  │  ├── update_realtime_discharge_configurable.py (~400 LOC)  │   │
│  │  └── Direct USGS API calls                                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Scheduling Layer (❌ Should be separate)                  │   │
│  │  ├── smart_scheduler.py (190 LOC)                          │   │
│  │  ├── Cron job management                                   │   │
│  │  └── Manual scheduling scripts                             │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Configuration Management (❌ Should be separate)          │   │
│  │  ├── json_config_manager.py (562 LOC)                      │   │
│  │  ├── config/default_configurations.json                    │   │
│  │  └── config/default_schedules.json                         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Database Layer (❌ Custom schema)                         │   │
│  │  ├── SQLite (usgs_data.db)                                 │   │
│  │  ├── unified_database_schema.sql (395 LOC)                 │   │
│  │  ├── 15 tables (stations, streamflow_data, configs, logs)  │   │
│  │  └── Custom repository pattern                             │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Admin Interface (❌ Mixed concerns)                       │   │
│  │  ├── admin_components.py (779 LOC)                         │   │
│  │  ├── Station management                                    │   │
│  │  ├── Collection monitoring                                 │   │
│  │  ├── Schedule management                                   │   │
│  │  └── Dashboard settings (only this should remain)          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Data Access Layer (⚠️ Needs refactoring)                 │   │
│  │  ├── data_manager.py (1,465 LOC - too complex)             │   │
│  │  ├── Direct USGS API fallback                              │   │
│  │  └── Multiple data sources handled locally                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Visualization Layer (✅ Good - Keep this)                 │   │
│  │  ├── app.py (1,777 LOC)                                    │   │
│  │  ├── Map components                                        │   │
│  │  ├── Chart components                                      │   │
│  │  ├── Filter panels                                         │   │
│  │  └── Water year utilities                                  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Problems:
❌ All responsibilities mixed in one application (~15,000 LOC)
❌ Data collection logic embedded in dashboard
❌ Cannot scale to multiple data sources easily
❌ Difficult to test components independently
❌ Admin interface manages both data AND UI concerns
❌ Maintenance requires touching multiple layers
```

---

## Target Architecture (Clean Separation of Concerns)

```
┌────────────────────────────────────────────────────────────────────────┐
│                     StreamFlow DataOps API                             │
│              (Dedicated Data Management System)                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Multi-Source Data Acquisition (Celery Tasks)                 │    │
│  │  ├── USGS collector (10,999 stations)                         │    │
│  │  ├── Environment Canada collector                             │    │
│  │  ├── NOAA collector                                           │    │
│  │  └── Extensible for future sources                            │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Intelligent Scheduling (Celery Beat)                         │    │
│  │  ├── PullConfiguration models                                 │    │
│  │  ├── Flexible cron schedules                                  │    │
│  │  └── Smart retry logic                                        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Data Persistence (PostgreSQL/SQLite)                         │    │
│  │  ├── Django ORM models                                        │    │
│  │  ├── Optimized schema                                         │    │
│  │  └── Redis caching                                            │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  REST API (24 endpoints)                                      │    │
│  │  ├── Stations API                                             │    │
│  │  ├── Observations API                                         │    │
│  │  ├── Configurations API                                       │    │
│  │  ├── Pagination, filtering, search                            │    │
│  │  └── Swagger documentation                                    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Admin Interface (Django)                                     │    │
│  │  ├── Station management                                       │    │
│  │  ├── Configuration management                                 │    │
│  │  ├── Execution logs                                           │    │
│  │  └── System monitoring                                        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              │ HTTP REST API (JSON)
                              │ http://localhost:8000/api/v1/
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                   DataOps Adapter Layer                              │
│              (Abstraction + Caching + Fallback)                      │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  DataOps Client Wrapper                                       │  │
│  │  ├── API communication                                        │  │
│  │  ├── Authentication                                           │  │
│  │  ├── Retry logic (3 attempts)                                 │  │
│  │  └── Error handling                                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Local Cache Manager                                          │  │
│  │  ├── SQLite cache (minimal schema)                            │  │
│  │  ├── 5-minute TTL (configurable)                              │  │
│  │  ├── Offline mode support                                     │  │
│  │  └── Cache invalidation                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Format Conversion Layer                                      │  │
│  │  ├── API JSON → Pandas DataFrame                              │  │
│  │  ├── Coordinate conversion                                    │  │
│  │  ├── Date/time handling                                       │  │
│  │  └── Unit conversion                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
                              │ Unified Python Interface
                              │ get_stations(), get_discharge_data()
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│              USGS Streamflow Dashboard                             │
│           (Pure Visualization Layer - Simplified)                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Simplified Data Manager (~400 LOC, was 1,465)           │    │
│  │  ├── Uses adapter only (no direct API calls)             │    │
│  │  ├── Format conversion                                   │    │
│  │  └── Data preparation for visualization                  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Minimal Dashboard Admin (~200 LOC, was 779)             │    │
│  │  ├── Display settings only                               │    │
│  │  ├── User preferences                                    │    │
│  │  ├── Theme configuration                                 │    │
│  │  └── Links to DataOps admin                              │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Visualization Components (Unchanged - ~6,000 LOC)       │    │
│  │  ├── app.py (Dash application)                           │    │
│  │  ├── Map components (Plotly)                             │    │
│  │  ├── Chart components (streamflow_analyzer)              │    │
│  │  ├── Filter panels                                       │    │
│  │  └── Water year utilities                                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘

Benefits:
✅ Clean separation of concerns (data vs. visualization)
✅ Dashboard simplified from ~15,000 to ~10,000 LOC (33% reduction)
✅ DataOps handles all data management centrally
✅ Easy to scale to multiple data sources
✅ Independent testing of each layer
✅ Adapter provides abstraction and caching
✅ Can work offline with cached data
✅ Clear ownership and maintenance boundaries
```

---

## Migration Path: Side-by-Side Comparison

### Phase 1: Add Adapter (No Breaking Changes)

```
Current System                    Adapter Added
    ↓                                ↓
┌─────────┐                    ┌─────────┐
│Dashboard│                    │Dashboard│
│  (OLD)  │                    │  (OLD)  │
└─────────┘                    └────┬────┘
                                    │
                               ┌────▼────┐
                               │ Adapter │ ← NEW
                               │(hybrid) │
                               └────┬────┘
                                    │
                             ┌──────┴──────┐
                             ↓             ↓
                        ┌────────┐    ┌────────┐
                        │DataOps │    │Local DB│
                        │  API   │    │(cache) │
                        └────────┘    └────────┘
```

### Phase 2: Refactor Dashboard (Uses Adapter)

```
Before                           After
    ↓                             ↓
┌──────────────┐            ┌──────────┐
│  Dashboard   │            │Dashboard │
│              │            │(refactor)│
│- Data collect│     →      │          │
│- Scheduling  │            │Viz only  │
│- Config mgmt │            │          │
│- Admin       │            └────┬─────┘
│- Database    │                 │
│- Viz         │            ┌────▼────┐
└──────────────┘            │ Adapter │
                            └────┬────┘
                                 │
                            ┌────▼────┐
                            │DataOps  │
                            │  API    │
                            └─────────┘
```

### Phase 3: Archive Old System (Clean)

```
Final State
    ↓
┌──────────────────────────────────┐
│        Dashboard                  │
│                                   │
│  ├── Visualization Components    │
│  ├── Minimal Admin (UI only)     │
│  └── Simplified Data Manager     │
│                                   │
│  Archive/                         │
│  ├── legacy_collectors/          │
│  ├── legacy_admin/               │
│  ├── legacy_config/              │
│  └── legacy_database/            │
└──────────┬───────────────────────┘
           │
           │ Uses Adapter
           │
┌──────────▼───────────┐
│   DataOps Adapter    │
│                      │
│  ├── Client Wrapper  │
│  ├── Cache Manager   │
│  └── Format Convert  │
└──────────┬───────────┘
           │
           │ REST API
           │
┌──────────▼───────────┐
│   DataOps System     │
│                      │
│  ├── Acquisition     │
│  ├── Storage         │
│  ├── API             │
│  └── Admin           │
└──────────────────────┘

Result: Clean separation, 33% less code, better maintainability
```

---

## Code Reduction Summary

### Files Removed/Archived

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Data Collection | 2,000 LOC | 0 LOC | -2,000 (100%) |
| Scheduling | 190 LOC | 0 LOC | -190 (100%) |
| Config Management | 900 LOC | 0 LOC | -900 (100%) |
| Admin Interface | 779 LOC | ~200 LOC | -579 (74%) |
| Database Code | 500 LOC | ~100 LOC | -400 (80%) |
| Data Manager | 1,465 LOC | ~400 LOC | -1,065 (73%) |
| **TOTAL** | **~15,000 LOC** | **~10,000 LOC** | **-5,000 (33%)** |

### Components Added

| Component | Lines of Code |
|-----------|---------------|
| DataOps Adapter Package | ~500 LOC |
| Adapter Tests | ~300 LOC |
| Integration Documentation | ~200 LOC |
| **TOTAL NEW** | **~1,000 LOC** |

**Net Reduction:** ~4,000 LOC (27% net reduction even with new adapter)

---

## Feature Comparison

| Feature | Current System | Target System |
|---------|---------------|---------------|
| Station Management | Dashboard (mixed) | DataOps (dedicated) |
| Data Collection | Dashboard scripts | DataOps (Celery) |
| Scheduling | Cron + smart_scheduler | Celery Beat |
| Multi-Source Support | USGS only | USGS + EC + NOAA |
| API Access | SQLite only | REST API + cache |
| Admin Interface | Mixed concerns | Separated (DataOps + Dashboard) |
| Visualization | Dash/Plotly | Dash/Plotly (unchanged) |
| Caching | Custom SQLite | Redis + local cache |
| Scalability | Limited (~1,500 stations) | High (10,999+ stations) |
| Testability | Difficult (coupled) | Easy (decoupled) |
| Maintenance | Complex | Simplified |

---

## Quick Reference: What Goes Where

### DataOps System Owns:
✅ Data collection from all sources  
✅ Station metadata management  
✅ Configuration management  
✅ Scheduling and task execution  
✅ Data persistence and storage  
✅ Admin interface for data operations  

### Dashboard Owns:
✅ Visualization components  
✅ User interface and UX  
✅ Chart and map rendering  
✅ Filter and search UI  
✅ Dashboard display settings  
✅ User preferences  

### Adapter Layer Owns:
✅ API communication  
✅ Local caching strategy  
✅ Format conversion  
✅ Offline mode fallback  
✅ Error handling  

---

**This diagram is for reference during the migration process.**  
**See [INTEGRATION_PLAN.md](./INTEGRATION_PLAN.md) for detailed migration steps.**
