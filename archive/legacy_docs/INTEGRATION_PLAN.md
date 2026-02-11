# StreamFlow Dashboard - DataOps Integration Plan

**Project:** Integration of StreamFlow DataOps into USGS Streamflow Dashboard  
**Date Created:** January 17, 2026  
**Status:** PLANNING  
**Estimated Duration:** 2-3 weeks  

---

## Executive Summary

This document provides a comprehensive plan for migrating the USGS Streamflow Dashboard from its embedded data management system to the new StreamFlow DataOps platform. The current dashboard suffers from **poor separation of concerns**, with data collection, storage, and visualization tightly coupled. This migration will:

1. **Archive the old embedded data management system** while preserving visualization capabilities
2. **Integrate the new DataOps API** as the single source of truth for streamflow data
3. **Improve maintainability** through clear separation of concerns
4. **Enable scalability** for future multi-source data integration

---

## Current System Analysis

### Problems Identified

#### 1. **Poor Separation of Concerns**
The dashboard currently mixes multiple responsibilities:

```
Current System (Monolithic)
├── Data Collection (configurable_data_collector.py, update_*_configurable.py)
├── Data Storage (SQLite database, custom schemas)
├── Configuration Management (json_config_manager.py, config/*.json)
├── Scheduling (smart_scheduler.py, cron scripts)
├── Admin Interface (admin_components.py)
├── Data Access Layer (usgs_dashboard/data/data_manager.py)
└── Visualization (usgs_dashboard/components/*)
```

**Issues:**
- Data collection logic embedded in dashboard codebase
- Duplicate data management in multiple places
- No centralized data governance
- Difficult to maintain and test
- Cannot easily switch data sources
- Admin panel manages both data AND visualization concerns

#### 2. **Duplicate/Overlapping Components**

| Component | Dashboard | DataOps | Issue |
|-----------|-----------|---------|-------|
| Station Management | stations table, JSONConfigManager | Station model, REST API | Duplicate station metadata |
| Data Collection | configurable_data_collector.py | Celery tasks, acquisition system | Redundant collection logic |
| Configuration | config/*.json files | PullConfiguration model | Different config systems |
| Scheduling | smart_scheduler.py, cron | Celery Beat, PullConfiguration | Two scheduling systems |
| Database Schema | unified_database_schema.sql | Django models | Different schemas |
| Admin Interface | admin_components.py | Django admin + custom views | Redundant admin panels |

#### 3. **Data Flow Architecture**

**Current (Problematic):**
```
USGS API → Dashboard Scripts → SQLite → data_manager → Visualization
            ↑
            └── Scheduler + Config Files
```

**Target (Clean):**
```
                    ┌─────────────────────────────────┐
                    │    StreamFlow DataOps API        │
                    │  (Data Collection + Management)  │
                    └─────────────┬───────────────────┘
                                  │ REST API
                    ┌─────────────▼───────────────────┐
                    │      DataAdapter Layer           │
                    │  (Abstraction + Local Cache)     │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │   Visualization Dashboard        │
                    │  (Pure Presentation Layer)       │
                    └──────────────────────────────────┘
```

---

## Integration Architecture

### Target System Structure

```
StreamFlow Dashboard (Post-Integration)
├── dataops_adapter/              # NEW: Adapter layer
│   ├── __init__.py
│   ├── client_adapter.py         # Wraps DataOps client
│   ├── cache_manager.py          # Local caching for performance
│   ├── config.py                 # Adapter configuration
│   └── exceptions.py             # Custom exceptions
│
├── usgs_dashboard/               # REFACTORED: Visualization only
│   ├── components/               # KEEP: Map, charts, filters
│   ├── utils/                    # KEEP: Water year calc, config
│   └── data/                     # SIMPLIFIED
│       └── data_manager.py       # REFACTORED: Uses adapter only
│
├── archive/                      # NEW: Old system archived
│   ├── legacy_collectors/        # MOVED: Old data collection
│   ├── legacy_admin/             # MOVED: Old admin components
│   ├── legacy_database/          # MOVED: Old database code
│   └── ARCHIVE_README.md         # Documentation of archived code
│
├── config/                       # SIMPLIFIED: UI settings only
│   └── dashboard_settings.json   # Display preferences, themes
│
├── app.py                        # REFACTORED: Uses adapter
├── requirements.txt              # UPDATED: Add dataops_client
├── .env                          # NEW: DataOps API config
└── README.md                     # UPDATED: Integration docs
```

### Key Design Principles

1. **Single Responsibility**: Dashboard does visualization, DataOps does data management
2. **Adapter Pattern**: Clean abstraction layer prevents tight coupling
3. **Fail-Safe**: Support local cache mode if API unavailable
4. **Backward Compatible**: Gradual migration with fallback options
5. **Minimal Changes**: Preserve existing visualization components

---

## Phase-by-Phase Migration Plan

### Phase 0: Preparation & Setup (2-3 days)

#### Objectives
- Backup current system
- Set up development environment
- Install DataOps client
- Create archive structure

#### Tasks

**0.1 Backup & Version Control**
```bash
# Create pre-migration backup
cd ~/Proj/streamflow-dashboard/usgs-streamflow-dashboard
git add -A
git commit -m "Pre-DataOps migration checkpoint"
git tag v1.0-pre-dataops-migration

# Backup database
cp data/usgs_data.db data/usgs_data.db.backup-$(date +%Y%m%d)

# Create migration branch
git checkout -b feature/dataops-integration
```

**0.2 Install DataOps Client**
```bash
# Install client library
cd ~/Proj/streamflow-dashboard/usgs-streamflow-dashboard
pip install -e ~/Proj/streamflow-dataOps/streamflow-dataOps/dataops_client

# Verify installation
python -c "from dataops_client import DataOpsClient; print('✓ Client installed')"
```

**0.3 Environment Configuration**
Create `.env` file:
```ini
# DataOps API Configuration
DATAOPS_API_URL=http://localhost:8000
DATAOPS_API_TOKEN=  # Optional for read-only
DATAOPS_VERIFY_SSL=true
DATAOPS_CACHE_ENABLED=true
DATAOPS_CACHE_TTL=300

# Feature Flags
USE_DATAOPS_API=false  # Start disabled for testing
ENABLE_LEGACY_ADMIN=true  # Keep old admin during transition
```

**0.4 Create Archive Structure**
```bash
# Create archive directory
mkdir -p archive/legacy_collectors
mkdir -p archive/legacy_admin
mkdir -p archive/legacy_database
mkdir -p archive/legacy_config
```

#### Deliverables
- [x] Git backup and new branch created
- [x] DataOps client installed and verified
- [x] Environment variables configured
- [x] Archive directory structure created
- [ ] Phase 0 documentation complete

---

### Phase 1: Adapter Layer Implementation (3-4 days)

#### Objectives
- Create adapter layer abstraction
- Implement local caching mechanism
- Build unified interface
- Test adapter with both modes

#### Architecture

```python
# dataops_adapter/client_adapter.py
class DataOpsAdapter:
    """
    Unified interface for data access.
    
    Modes:
    1. API mode: Uses DataOps API
    2. Cache mode: Uses local SQLite cache
    3. Hybrid mode: API with local fallback
    """
    
    def __init__(self, mode='hybrid'):
        self.mode = mode
        self.api_client = None
        self.local_cache = None
        
    def get_stations(self, filters: StationFilters) -> List[Station]:
        """Get station metadata."""
        pass
        
    def get_discharge_data(
        self, 
        station_id: str,
        start_date: datetime,
        end_date: datetime,
        data_type: str = 'daily_mean'
    ) -> pd.DataFrame:
        """Get discharge observations."""
        pass
        
    def get_realtime_data(
        self,
        station_id: str,
        hours_back: int = 48
    ) -> pd.DataFrame:
        """Get real-time 15-minute data."""
        pass
```

#### Tasks

**1.1 Create Adapter Package**
```bash
mkdir -p dataops_adapter
touch dataops_adapter/__init__.py
touch dataops_adapter/client_adapter.py
touch dataops_adapter/cache_manager.py
touch dataops_adapter/models.py
touch dataops_adapter/config.py
touch dataops_adapter/exceptions.py
```

**1.2 Implement Client Adapter**
- Wrap DataOps client with unified interface
- Implement connection management
- Add error handling and retries
- Create data format converters

**1.3 Implement Cache Manager**
- Local SQLite cache for performance
- Cache invalidation strategy
- Fallback mechanism when API unavailable
- Cache synchronization utilities

**1.4 Create Data Models**
- Define common data structures
- Type hints for all interfaces
- Validation logic
- Conversion utilities (API format ↔ Dashboard format)

**1.5 Write Unit Tests**
```python
# tests/test_adapter.py
def test_adapter_api_mode():
    """Test adapter in API mode."""
    pass
    
def test_adapter_cache_mode():
    """Test adapter with local cache."""
    pass
    
def test_adapter_hybrid_mode():
    """Test hybrid mode with fallback."""
    pass
    
def test_data_format_conversion():
    """Test format conversions."""
    pass
```

#### Deliverables
- [ ] Adapter package structure created
- [ ] Client adapter implemented (API mode)
- [ ] Cache manager implemented (local mode)
- [ ] Hybrid mode with fallback working
- [ ] Unit tests passing (>80% coverage)
- [ ] Documentation for adapter usage

---

### Phase 2: Data Manager Refactoring (2-3 days)

#### Objectives
- Refactor data_manager.py to use adapter
- Remove embedded data collection logic
- Simplify data access layer
- Maintain backward compatibility

#### Current vs Target

**Current: `usgs_dashboard/data/data_manager.py`**
```python
class USGSDataManager:
    """Monolithic data manager with embedded collection."""
    
    def load_regional_gauges(self, refresh=False):
        """Fetches from USGS API directly."""
        # 500+ lines of data collection logic
        # Caching, validation, metadata enrichment
        # All mixed together
```

**Target: `usgs_dashboard/data/data_manager.py`**
```python
from dataops_adapter import DataOpsAdapter

class USGSDataManager:
    """Lightweight data manager using adapter."""
    
    def __init__(self):
        self.adapter = DataOpsAdapter(mode='hybrid')
    
    def load_regional_gauges(self, refresh=False):
        """Load stations from DataOps."""
        return self.adapter.get_stations(
            filters={'states': ['OR', 'WA', 'ID']}
        )
    
    def get_streamflow_data(self, site_id, start_date, end_date):
        """Get discharge data."""
        return self.adapter.get_discharge_data(
            station_id=site_id,
            start_date=start_date,
            end_date=end_date
        )
```

#### Tasks

**2.1 Analyze Current Data Manager**
- Map all public methods
- Identify data sources (USGS API calls)
- Document expected return formats
- List dependencies on old database

**2.2 Refactor Station Loading**
- Replace `load_regional_gauges()` with adapter calls
- Update metadata processing
- Maintain DataFrame format for components
- Remove USGS API direct calls

**2.3 Refactor Data Retrieval**
- Replace streamflow data queries
- Replace realtime data queries
- Update statistical calculations
- Maintain compatibility with viz components

**2.4 Update Repository Layer**
If using repositories:
```python
# Remove: usgs_dashboard/data/database/
# These are now handled by DataOps
```

**2.5 Integration Tests**
```python
# tests/test_data_manager.py
def test_data_manager_with_adapter():
    """Test data manager using adapter."""
    pass
    
def test_backward_compatibility():
    """Ensure existing components still work."""
    pass
```

#### Deliverables
- [ ] data_manager.py refactored (50% reduction in code)
- [ ] All USGS API calls removed
- [ ] Adapter integration complete
- [ ] Repository pattern simplified
- [ ] Integration tests passing
- [ ] Performance benchmarks documented

---

### Phase 3: Archive Old System (1-2 days)

#### Objectives
- Move old data collection code to archive
- Preserve for reference and rollback
- Document what was archived and why
- Clean up main codebase

#### Files to Archive

**Data Collection Scripts** → `archive/legacy_collectors/`
- `configurable_data_collector.py`
- `update_daily_discharge_configurable.py`
- `update_realtime_discharge_configurable.py`
- `smart_scheduler.py`
- `setup_scheduling.sh`
- `setup_crontab.sh`

**Admin Components** → `archive/legacy_admin/`
- `admin_components.py` (station management, collection monitoring)
- Keep minimal admin for dashboard-only settings

**Configuration Management** → `archive/legacy_config/`
- `json_config_manager.py`
- `config/default_configurations.json`
- `config/default_schedules.json`
- Keep `config/dashboard_settings.json` for UI settings

**Database Code** → `archive/legacy_database/`
- `unified_database_schema.sql`
- `usgs_dashboard/data/database/` (repositories, schema_manager)
- Keep minimal code for local cache

**Documentation** → Update in place
- Add `ARCHIVED_COMPONENTS.md` to archive/
- Update main README.md
- Update ARCHITECTURE.md

#### Tasks

**3.1 Create Archive Documentation**
```markdown
# archive/ARCHIVED_COMPONENTS.md

## Archived Components - DataOps Migration

### Data Collection System
**Archived:** January 17, 2026  
**Reason:** Replaced by StreamFlow DataOps API

#### Files Archived:
- configurable_data_collector.py (819 lines)
- update_daily_discharge_configurable.py (439 lines)
- update_realtime_discharge_configurable.py (XXX lines)
- smart_scheduler.py (190 lines)

#### Replacement:
Data collection now handled by:
- DataOps API: http://localhost:8000
- Celery tasks in DataOps backend
- PullConfiguration models

#### Rollback Procedure:
If needed to restore old system:
1. Copy files from archive/ back to root
2. Restore database: `cp data/usgs_data.db.backup data/usgs_data.db`
3. Set USE_DATAOPS_API=false in .env
4. Re-enable cron jobs

...
```

**3.2 Move Files to Archive**
```bash
# Move data collection
mv configurable_data_collector.py archive/legacy_collectors/
mv update_*_discharge_configurable.py archive/legacy_collectors/
mv smart_scheduler.py archive/legacy_collectors/
mv setup_*.sh archive/legacy_collectors/

# Move admin (keep minimal dashboard admin)
mv admin_components.py archive/legacy_admin/
# TODO: Create new simplified dashboard_admin.py

# Move config management
mv json_config_manager.py archive/legacy_config/
mv config/default_configurations.json archive/legacy_config/
mv config/default_schedules.json archive/legacy_config/

# Move database code
mv unified_database_schema.sql archive/legacy_database/
# Keep minimal cache schema
```

**3.3 Update Imports**
- Search for imports of archived modules
- Replace with adapter equivalents
- Update all references in codebase

**3.4 Update Documentation**
- Update README.md with new architecture
- Update ARCHITECTURE.md
- Create migration guide for developers
- Update deployment documentation

#### Deliverables
- [ ] All legacy files moved to archive/
- [ ] Archive documentation complete
- [ ] Codebase imports updated
- [ ] Main README updated
- [ ] No broken imports remain

---

### Phase 4: Admin Interface Redesign (2-3 days)

#### Objectives
- Remove data management from dashboard admin
- Create minimal dashboard-only admin
- Redirect data management to DataOps web interface
- Maintain user experience continuity

#### Current vs Target

**Current Admin** (admin_components.py - 779 lines)
- ❌ Station configuration management
- ❌ Collection scheduling
- ❌ Data collection monitoring
- ❌ Station browser and editing
- ✅ Dashboard settings
- ✅ User preferences

**Target Admin** (dashboard_admin.py - ~200 lines)
- ✅ Dashboard display settings
- ✅ User preferences
- ✅ Visualization configuration
- ✅ Theme/color settings
- ➡️ Link to DataOps admin for data management

#### New Structure

```python
# dashboard_admin.py
class DashboardAdmin:
    """Minimal admin for dashboard-only settings."""
    
    def create_settings_panel(self):
        """Dashboard display settings."""
        return dbc.Card([
            # Color schemes
            # Default states/regions to show
            # Map zoom levels
            # Chart preferences
        ])
    
    def create_api_status_panel(self):
        """Show DataOps API connection status."""
        return dbc.Card([
            # API health check
            # Last data update
            # Link to DataOps admin
        ])
```

#### Tasks

**4.1 Create New Dashboard Admin**
- Design minimal admin interface
- Dashboard settings only
- API connection status
- Link to DataOps for data management

**4.2 Create DataOps Admin Links**
```python
# Add prominent links to DataOps interface
DATAOPS_ADMIN_LINKS = {
    'stations': 'http://localhost:8000/admin/streamflow/station/',
    'configurations': 'http://localhost:8000/streamflow/configurations/',
    'logs': 'http://localhost:8000/streamflow/execution-logs/',
    'dashboard': 'http://localhost:8000/streamflow/',
}
```

**4.3 Simplify Admin Interface**
- Remove station management components
- Remove collection monitoring
- Remove schedule management
- Keep only dashboard preferences

**4.4 Update App.py**
- Remove old admin imports
- Add new dashboard admin
- Update callbacks
- Simplify authentication (if still needed)

#### Deliverables
- [ ] New dashboard_admin.py created
- [ ] Old admin_components.py archived
- [ ] DataOps admin links integrated
- [ ] app.py updated
- [ ] User documentation updated

---

### Phase 5: Testing & Validation (2-3 days)

#### Objectives
- Comprehensive testing of integrated system
- Performance benchmarking
- Data accuracy validation
- User acceptance testing

#### Test Categories

**5.1 Unit Tests**
- Adapter layer (all modes)
- Data format conversions
- Cache management
- Error handling

**5.2 Integration Tests**
- End-to-end data flow
- API → Adapter → DataManager → Visualization
- Cache synchronization
- Fallback mechanisms

**5.3 Performance Tests**
```python
# tests/test_performance.py
def test_station_loading_performance():
    """API mode vs cache mode performance."""
    pass
    
def test_data_query_performance():
    """Compare query times."""
    pass
    
def test_concurrent_requests():
    """Test under load."""
    pass
```

**5.4 Data Validation**
```python
# tests/test_data_accuracy.py
def test_data_consistency():
    """Compare old system vs new system data."""
    # Load same station/date range from both
    # Verify discharge values match
    pass
```

**5.5 User Acceptance Testing**
- Dashboard loads correctly
- All visualizations work
- Map displays stations
- Data filters work
- Charts render properly
- No performance degradation

#### Tasks

**5.1 Write Test Suite**
- Unit tests for adapter
- Integration tests for data flow
- Performance benchmarks
- Data validation tests

**5.2 Execute Tests**
```bash
# Run all tests
pytest tests/ -v --cov=dataops_adapter --cov=usgs_dashboard

# Performance benchmarks
python tests/benchmark_performance.py

# Data validation
python tests/validate_data_accuracy.py
```

**5.3 Fix Issues**
- Address test failures
- Optimize performance bottlenecks
- Fix data inconsistencies
- Update documentation

**5.4 User Testing**
- Deploy to staging environment
- Test with real users
- Collect feedback
- Iterate on UX issues

#### Deliverables
- [ ] Test suite complete (>80% coverage)
- [ ] All tests passing
- [ ] Performance benchmarks documented
- [ ] Data accuracy validated
- [ ] User feedback incorporated
- [ ] Test report published

---

### Phase 6: Production Deployment (1-2 days)

#### Objectives
- Deploy integrated system to production
- Monitor performance and stability
- Ensure rollback capability
- Document deployment process

#### Pre-Deployment Checklist

**Code Quality**
- [ ] All tests passing
- [ ] Code review complete
- [ ] Documentation updated
- [ ] No linting errors

**Configuration**
- [ ] Production .env configured
- [ ] DataOps API URL set correctly
- [ ] Caching configured appropriately
- [ ] Feature flags set

**Infrastructure**
- [ ] DataOps API running and healthy
- [ ] Database backups recent
- [ ] Monitoring configured
- [ ] Alerts set up

**Rollback Plan**
- [ ] Backup procedures documented
- [ ] Rollback script tested
- [ ] Old system available in archive
- [ ] Quick rollback possible (<5 minutes)

#### Deployment Steps

**6.1 Final Testing**
```bash
# Staging environment
export USE_DATAOPS_API=true
export DATAOPS_API_URL=https://api-staging.dataops.example.com
python -m pytest tests/ -v

# Load test
python tests/load_test.py --duration 300
```

**6.2 Production Deployment**
```bash
# Backup
./scripts/backup_before_deploy.sh

# Deploy
git checkout main
git merge feature/dataops-integration
git tag v2.0-dataops-integrated

# Update environment
cp .env.production .env

# Restart services
./scripts/restart_dashboard.sh

# Verify
curl http://localhost:5000/health
```

**6.3 Post-Deployment Monitoring**
- Monitor API response times
- Check error logs
- Verify data updates
- Watch memory usage
- Confirm user sessions active

**6.4 Rollback Procedure (if needed)**
```bash
# Quick rollback script
./scripts/rollback_to_legacy.sh

# Manual rollback
git checkout v1.0-pre-dataops-migration
cp data/usgs_data.db.backup data/usgs_data.db
echo "USE_DATAOPS_API=false" > .env
./scripts/restart_dashboard.sh
```

#### Deliverables
- [ ] Production deployment successful
- [ ] All services healthy
- [ ] Monitoring active
- [ ] Users notified
- [ ] Rollback plan tested
- [ ] Deployment documented

---

## Rollback Strategy

### Quick Rollback (<5 minutes)

```bash
#!/bin/bash
# scripts/rollback_to_legacy.sh

echo "🔄 Rolling back to legacy system..."

# 1. Switch environment
cp .env.legacy .env

# 2. Restore database
cp data/usgs_data.db.backup data/usgs_data.db

# 3. Revert code (if needed)
git checkout v1.0-pre-dataops-migration

# 4. Restart
./scripts/restart_dashboard.sh

echo "✅ Rollback complete. Legacy system active."
```

### Full Rollback (if adapter problematic)

1. **Restore archived files**
   ```bash
   cp archive/legacy_collectors/* .
   cp archive/legacy_admin/admin_components.py .
   cp archive/legacy_config/* config/
   ```

2. **Restore database schema**
   ```bash
   sqlite3 data/usgs_data.db < archive/legacy_database/unified_database_schema.sql
   ```

3. **Restore cron jobs**
   ```bash
   crontab -l > crontab.backup
   cat archive/legacy_collectors/crontab.txt | crontab -
   ```

---

## Risk Management

### Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| API downtime | Medium | High | Local cache fallback, monitoring alerts |
| Data format mismatches | Low | High | Extensive testing, validation scripts |
| Performance degradation | Medium | Medium | Benchmarking, caching strategy |
| User resistance | Low | Medium | Training, documentation, gradual rollout |
| Migration bugs | Medium | High | Staged rollout, comprehensive testing |
| Data loss | Low | Critical | Backups before each phase |

### Mitigation Strategies

**1. Local Cache Fallback**
- Adapter always uses local cache first
- API called only for updates
- Dashboard works offline with cached data

**2. Gradual Feature Flag Rollout**
```python
# Progressive enablement
Week 1: USE_DATAOPS_API=false  # All legacy
Week 2: USE_DATAOPS_API=true, CACHE_MODE=aggressive  # API with heavy caching
Week 3: USE_DATAOPS_API=true, CACHE_MODE=normal  # Normal operation
```

**3. Monitoring & Alerts**
```python
# Health check endpoint
@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'api_mode': os.getenv('USE_DATAOPS_API'),
        'api_reachable': adapter.test_connection(),
        'cache_hits': adapter.cache.get_stats(),
        'last_update': adapter.cache.last_update_time(),
    }
```

---

## Success Metrics

### Technical Metrics

| Metric | Baseline (Current) | Target (Post-Migration) |
|--------|-------------------|------------------------|
| Lines of Code | ~15,000 | <10,000 (33% reduction) |
| Data Collection Code | ~2,000 lines | 0 (moved to DataOps) |
| Database Tables | 15 tables | 2 tables (cache only) |
| Admin Interface LOC | 779 lines | <200 lines |
| API Response Time | N/A | <100ms (cached), <500ms (API) |
| Test Coverage | ~40% | >80% |

### Operational Metrics

| Metric | Target |
|--------|--------|
| Dashboard Load Time | <2 seconds |
| Data Freshness | <15 minutes |
| API Uptime | >99% |
| Zero Data Loss | 100% |
| Rollback Time | <5 minutes |

### User Experience Metrics

| Metric | Target |
|--------|--------|
| Feature Parity | 100% |
| User Training Required | <1 hour |
| User Satisfaction | >4/5 |
| Bug Reports | <5 in first week |

---

## Timeline Summary

| Phase | Duration | Dependencies | Deliverables |
|-------|----------|--------------|--------------|
| 0. Preparation | 2-3 days | None | Backup, client install, env setup |
| 1. Adapter Layer | 3-4 days | Phase 0 | Adapter package, tests |
| 2. Data Manager | 2-3 days | Phase 1 | Refactored data_manager.py |
| 3. Archive Old System | 1-2 days | Phase 2 | Files archived, docs updated |
| 4. Admin Redesign | 2-3 days | Phase 3 | New dashboard admin |
| 5. Testing | 2-3 days | Phase 4 | Test suite, validation |
| 6. Deployment | 1-2 days | Phase 5 | Production deployment |

**Total Estimated Duration:** 13-20 days (2-3 weeks)

**Critical Path:** Phase 0 → 1 → 2 → 5 → 6

---

## Post-Migration Maintenance

### Ongoing Tasks

**Weekly**
- Monitor API health and performance
- Review error logs
- Check cache hit rates
- Verify data freshness

**Monthly**
- Update dataops_client library
- Review and optimize caching strategy
- Analyze performance metrics
- User feedback review

**Quarterly**
- Full system audit
- Update documentation
- Dependency updates
- Security review

---

## Appendix

### A. File Mapping (Before → After)

| Old File | New Location | Status |
|----------|-------------|--------|
| configurable_data_collector.py | archive/legacy_collectors/ | Archived |
| update_daily_discharge_configurable.py | archive/legacy_collectors/ | Archived |
| update_realtime_discharge_configurable.py | archive/legacy_collectors/ | Archived |
| smart_scheduler.py | archive/legacy_collectors/ | Archived |
| admin_components.py | archive/legacy_admin/ | Archived |
| json_config_manager.py | archive/legacy_config/ | Archived |
| unified_database_schema.sql | archive/legacy_database/ | Archived |
| usgs_dashboard/data/data_manager.py | usgs_dashboard/data/data_manager.py | Refactored |
| usgs_dashboard/data/database/* | archive/legacy_database/ | Archived |
| config/default_configurations.json | archive/legacy_config/ | Archived |
| config/default_schedules.json | archive/legacy_config/ | Archived |
| - | dataops_adapter/* | New |
| - | dashboard_admin.py | New |
| - | config/dashboard_settings.json | New |

### B. Dependencies to Add

```txt
# requirements.txt additions
dataops-client>=1.0.0
python-dotenv>=1.0.0
requests-cache>=1.0.0  # For adapter caching
```

### C. Environment Variables

```ini
# .env.example
# DataOps API Configuration
DATAOPS_API_URL=http://localhost:8000
DATAOPS_API_TOKEN=optional-for-read-only
DATAOPS_VERIFY_SSL=true
DATAOPS_CACHE_ENABLED=true
DATAOPS_CACHE_TTL=300
DATAOPS_TIMEOUT=30

# Feature Flags
USE_DATAOPS_API=false
ENABLE_LEGACY_ADMIN=false
DEBUG_MODE=false

# Dashboard Settings
DASHBOARD_TITLE=USGS Streamflow Dashboard
DEFAULT_STATES=OR,WA,ID
DEFAULT_ZOOM=6
```

### D. Key Contacts

| Role | Contact | Responsibility |
|------|---------|----------------|
| Dashboard Lead | [Name] | Dashboard integration, testing |
| DataOps Lead | [Name] | API support, troubleshooting |
| DevOps | [Name] | Deployment, monitoring |
| QA Lead | [Name] | Test strategy, validation |

---

## Approval & Sign-Off

| Stakeholder | Role | Date | Signature |
|-------------|------|------|-----------|
| [Name] | Project Lead | | |
| [Name] | Technical Lead | | |
| [Name] | Product Owner | | |

---

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Next Review:** Start of Phase 0
