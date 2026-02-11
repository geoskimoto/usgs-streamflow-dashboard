# Quick Start Guide: DataOps Integration

**For Developers Implementing the Migration**

---

## Prerequisites

✅ You've read [INTEGRATION_ANALYSIS_SUMMARY.md](./INTEGRATION_ANALYSIS_SUMMARY.md)  
✅ You've reviewed [INTEGRATION_PLAN.md](./INTEGRATION_PLAN.md)  
✅ You understand [ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md)  
✅ You have access to both repositories

---

## Day 1: Setup & Preparation

### 1. Create Backup

```bash
cd ~/Proj/streamflow-dashboard/usgs-streamflow-dashboard

# Git checkpoint
git add -A
git commit -m "Pre-DataOps migration checkpoint"
git tag v1.0-pre-dataops-migration

# Database backup
timestamp=$(date +%Y%m%d-%H%M%S)
cp data/usgs_data.db "data/usgs_data.db.backup-${timestamp}"

# Create feature branch
git checkout -b feature/dataops-integration
```

### 2. Install DataOps Client

```bash
# Install from source
pip install -e ~/Proj/streamflow-dataOps/streamflow-dataOps/dataops_client

# Verify
python -c "from dataops_client import DataOpsClient; print('✓ Installed')"
```

### 3. Configure Environment

```bash
# Create .env file
cat > .env << 'EOF'
# DataOps API Configuration
DATAOPS_API_URL=http://localhost:8000
DATAOPS_API_TOKEN=
DATAOPS_VERIFY_SSL=true
DATAOPS_CACHE_ENABLED=true
DATAOPS_CACHE_TTL=300

# Feature Flags (start disabled)
USE_DATAOPS_API=false
ENABLE_LEGACY_ADMIN=true
EOF

# Load environment in Python
pip install python-dotenv
```

### 4. Verify DataOps API is Running

```bash
# Check API health
curl http://localhost:8000/api/v1/health/

# Expected response:
# {"status": "healthy", "database": "connected", ...}

# Browse API docs
open http://localhost:8000/api/docs/  # macOS
# or
xdg-open http://localhost:8000/api/docs/  # Linux
```

---

## Day 2-4: Build Adapter Layer

### 1. Create Package Structure

```bash
mkdir -p dataops_adapter
touch dataops_adapter/__init__.py
touch dataops_adapter/client_adapter.py
touch dataops_adapter/cache_manager.py
touch dataops_adapter/models.py
touch dataops_adapter/config.py
touch dataops_adapter/exceptions.py
```

### 2. Implement Client Adapter

**File:** `dataops_adapter/client_adapter.py`

```python
"""
DataOps Client Adapter

Unified interface for dashboard to access streamflow data.
Supports API mode, cache mode, and hybrid mode.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
from dataops_client import DataOpsClient
from .cache_manager import CacheManager
from .models import Station, DischargeObservation
from .exceptions import AdapterError, APIError, CacheError


class DataOpsAdapter:
    """
    Adapter for accessing streamflow data.
    
    Usage:
        adapter = DataOpsAdapter(mode='hybrid')
        stations = adapter.get_stations(state='CO')
        data = adapter.get_discharge_data('09070500', '2026-01-01', '2026-01-17')
    """
    
    def __init__(self, mode: str = 'hybrid'):
        """
        Initialize adapter.
        
        Args:
            mode: 'api', 'cache', or 'hybrid'
        """
        self.mode = mode
        self.api_enabled = mode in ('api', 'hybrid')
        self.cache_enabled = mode in ('cache', 'hybrid')
        
        # Initialize API client
        if self.api_enabled:
            self.api_client = DataOpsClient(
                base_url=os.getenv('DATAOPS_API_URL', 'http://localhost:8000'),
                api_token=os.getenv('DATAOPS_API_TOKEN'),
                cache_enabled=False,  # We handle caching
                verify_ssl=os.getenv('DATAOPS_VERIFY_SSL', 'true').lower() == 'true'
            )
        
        # Initialize cache manager
        if self.cache_enabled:
            self.cache = CacheManager(
                db_path='data/dataops_cache.db',
                ttl=int(os.getenv('DATAOPS_CACHE_TTL', '300'))
            )
    
    def get_stations(
        self,
        state: Optional[str] = None,
        agency: str = 'USGS',
        is_active: bool = True,
        search: Optional[str] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Get list of stations.
        
        Returns DataFrame with columns:
        - station_number (str)
        - name (str)
        - agency (str)
        - latitude (float)
        - longitude (float)
        - state (str)
        - huc_code (str)
        - is_active (bool)
        """
        # Try cache first
        if self.cache_enabled:
            cached = self.cache.get_stations(state=state, agency=agency)
            if cached is not None:
                return cached
        
        # Fetch from API
        if self.api_enabled:
            try:
                response = self.api_client.get_stations(
                    state=state,
                    agency=agency,
                    is_active=is_active,
                    search=search,
                    limit=limit
                )
                
                # Convert to DataFrame
                df = self._stations_to_dataframe(response.results)
                
                # Update cache
                if self.cache_enabled:
                    self.cache.set_stations(df, state=state, agency=agency)
                
                return df
                
            except Exception as e:
                # Try cache as fallback
                if self.cache_enabled:
                    cached = self.cache.get_stations(state=state, agency=agency)
                    if cached is not None:
                        return cached
                raise APIError(f"Failed to fetch stations: {e}")
        
        raise AdapterError("No data source available (API and cache both unavailable)")
    
    def get_discharge_data(
        self,
        station_number: str,
        start_date: str,
        end_date: str,
        data_type: str = 'daily_mean'
    ) -> pd.DataFrame:
        """
        Get discharge observations.
        
        Returns DataFrame with columns:
        - date (datetime)
        - station_number (str)
        - discharge (float)
        - unit (str)
        - quality (str)
        """
        # Try cache first
        if self.cache_enabled:
            cached = self.cache.get_discharge_data(
                station_number, start_date, end_date, data_type
            )
            if cached is not None:
                return cached
        
        # Fetch from API
        if self.api_enabled:
            try:
                observations = self.api_client.get_station_data(
                    station_number=station_number,
                    start_date=start_date,
                    end_date=end_date,
                    data_type=data_type
                )
                
                # Convert to DataFrame
                df = self._observations_to_dataframe(observations)
                
                # Update cache
                if self.cache_enabled:
                    self.cache.set_discharge_data(
                        df, station_number, start_date, end_date, data_type
                    )
                
                return df
                
            except Exception as e:
                # Try cache as fallback
                if self.cache_enabled:
                    cached = self.cache.get_discharge_data(
                        station_number, start_date, end_date, data_type
                    )
                    if cached is not None:
                        return cached
                raise APIError(f"Failed to fetch discharge data: {e}")
        
        raise AdapterError("No data source available")
    
    def _stations_to_dataframe(self, stations: List) -> pd.DataFrame:
        """Convert API station objects to DataFrame."""
        data = []
        for station in stations:
            data.append({
                'station_number': station.station_number,
                'name': station.name,
                'agency': station.agency,
                'latitude': float(station.latitude) if station.latitude else None,
                'longitude': float(station.longitude) if station.longitude else None,
                'state': station.state_code,
                'huc_code': station.huc_code,
                'is_active': station.is_active,
            })
        return pd.DataFrame(data)
    
    def _observations_to_dataframe(self, observations: List) -> pd.DataFrame:
        """Convert API observation objects to DataFrame."""
        data = []
        for obs in observations:
            data.append({
                'date': pd.to_datetime(obs.observed_at),
                'station_number': obs.station_number,
                'discharge': obs.discharge_value,
                'unit': obs.unit,
                'quality': obs.quality_code,
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('date')
        return df
    
    def test_connection(self) -> bool:
        """Test API connection."""
        if not self.api_enabled:
            return False
        try:
            # Try a simple API call
            self.api_client.get_stations(limit=1)
            return True
        except:
            return False
```

### 3. Implement Cache Manager

**File:** `dataops_adapter/cache_manager.py`

```python
"""Local SQLite cache for DataOps data."""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


class CacheManager:
    """Manages local SQLite cache."""
    
    def __init__(self, db_path: str, ttl: int = 300):
        self.db_path = db_path
        self.ttl = ttl  # seconds
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Stations cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_stations (
                cache_key TEXT PRIMARY KEY,
                data BLOB,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Discharge cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_discharge (
                station_number TEXT,
                start_date TEXT,
                end_date TEXT,
                data_type TEXT,
                data BLOB,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (station_number, start_date, end_date, data_type)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_stations(self, state: Optional[str] = None, agency: str = 'USGS') -> Optional[pd.DataFrame]:
        """Get cached stations."""
        cache_key = f"stations:{agency}:{state or 'all'}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT data, cached_at FROM cache_stations WHERE cache_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        data_blob, cached_at = row
        cached_time = datetime.fromisoformat(cached_at)
        
        # Check if expired
        if datetime.now() - cached_time > timedelta(seconds=self.ttl):
            return None
        
        # Deserialize
        return pd.read_json(data_blob)
    
    def set_stations(self, df: pd.DataFrame, state: Optional[str] = None, agency: str = 'USGS'):
        """Cache stations."""
        cache_key = f"stations:{agency}:{state or 'all'}"
        data_blob = df.to_json()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO cache_stations (cache_key, data, cached_at) VALUES (?, ?, ?)",
            (cache_key, data_blob, datetime.now())
        )
        
        conn.commit()
        conn.close()
    
    # Similar methods for discharge data...
```

### 4. Write Tests

**File:** `tests/test_adapter.py`

```python
"""Tests for DataOps adapter."""

import pytest
import os
from dataops_adapter import DataOpsAdapter


def test_adapter_initialization():
    """Test adapter initializes correctly."""
    adapter = DataOpsAdapter(mode='hybrid')
    assert adapter.mode == 'hybrid'
    assert adapter.api_enabled
    assert adapter.cache_enabled


def test_get_stations():
    """Test get_stations method."""
    os.environ['USE_DATAOPS_API'] = 'true'
    adapter = DataOpsAdapter(mode='api')
    
    stations = adapter.get_stations(state='CO', limit=5)
    assert len(stations) > 0
    assert 'station_number' in stations.columns
    assert 'name' in stations.columns


def test_get_discharge_data():
    """Test get_discharge_data method."""
    adapter = DataOpsAdapter(mode='api')
    
    data = adapter.get_discharge_data(
        station_number='09070500',
        start_date='2026-01-01',
        end_date='2026-01-17'
    )
    assert len(data) > 0
    assert 'date' in data.columns
    assert 'discharge' in data.columns


# Run tests
pytest.main([__file__, '-v'])
```

---

## Day 5-7: Refactor Data Manager

### Update data_manager.py

**File:** `usgs_dashboard/data/data_manager.py`

**Before (current):**
```python
class USGSDataManager:
    def load_regional_gauges(self, refresh=False):
        # 500+ lines of USGS API calls, caching, validation...
        pass
```

**After (refactored):**
```python
from dataops_adapter import DataOpsAdapter

class USGSDataManager:
    def __init__(self):
        self.adapter = DataOpsAdapter(mode='hybrid')
    
    def load_regional_gauges(self, refresh=False):
        """Load gauges using DataOps adapter."""
        return self.adapter.get_stations(
            agency='USGS',
            state=None,  # All states
            is_active=True
        )
    
    def get_streamflow_data(self, site_id, start_date, end_date):
        """Get discharge data."""
        return self.adapter.get_discharge_data(
            station_number=site_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            data_type='daily_mean'
        )
```

---

## Day 8-9: Archive Old System

### Move Files to Archive

```bash
# Create archive directories
mkdir -p archive/legacy_collectors
mkdir -p archive/legacy_admin
mkdir -p archive/legacy_config
mkdir -p archive/legacy_database

# Move data collection
mv configurable_data_collector.py archive/legacy_collectors/
mv update_*_discharge_configurable.py archive/legacy_collectors/
mv smart_scheduler.py archive/legacy_collectors/

# Move config management
mv json_config_manager.py archive/legacy_config/
mv config/default_configurations.json archive/legacy_config/
mv config/default_schedules.json archive/legacy_config/

# Move admin
mv admin_components.py archive/legacy_admin/

# Move database
mv unified_database_schema.sql archive/legacy_database/

# Create archive README
cat > archive/README.md << 'EOF'
# Archived Components

These components were archived during the DataOps integration
migration on $(date +%Y-%m-%d).

See ../INTEGRATION_PLAN.md for details.
EOF

# Commit
git add archive/
git commit -m "Archive old data management system"
```

---

## Day 10-11: Testing

### Run Test Suite

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v --cov=dataops_adapter --cov=usgs_dashboard

# Performance test
python tests/benchmark_performance.py

# Data validation
python tests/validate_data_accuracy.py
```

### Manual Testing Checklist

- [ ] Dashboard loads correctly
- [ ] Map displays stations
- [ ] Station selection works
- [ ] Charts render properly
- [ ] Data filters work
- [ ] Real-time data updates
- [ ] Cache fallback works (disconnect API)
- [ ] Performance acceptable (<2s load time)

---

## Day 12: Deployment

### Enable API Mode

```bash
# Update .env
sed -i 's/USE_DATAOPS_API=false/USE_DATAOPS_API=true/' .env

# Restart dashboard
./scripts/restart_dashboard.sh

# Verify
curl http://localhost:5000/health
```

### Monitor

```bash
# Watch logs
tail -f logs/dashboard.log

# Check API health
watch -n 5 'curl -s http://localhost:8000/api/v1/health/ | jq'

# Monitor cache hits
python scripts/monitor_cache.py
```

---

## Rollback (If Needed)

### Quick Rollback

```bash
# Disable API mode
sed -i 's/USE_DATAOPS_API=true/USE_DATAOPS_API=false/' .env

# Restore database
cp data/usgs_data.db.backup-* data/usgs_data.db

# Restart
./scripts/restart_dashboard.sh
```

### Full Rollback

```bash
# Revert to pre-migration
git checkout v1.0-pre-dataops-migration

# Restore files from archive
cp archive/legacy_collectors/* .
cp archive/legacy_admin/admin_components.py .
cp archive/legacy_config/*.json config/

# Restart
./scripts/restart_dashboard.sh
```

---

## Common Issues & Solutions

### Issue: API Connection Refused

```bash
# Check API is running
curl http://localhost:8000/api/v1/health/

# If not running, start DataOps:
cd ~/Proj/streamflow-dataOps/streamflow-dataOps
python manage.py runserver
```

### Issue: Import Errors

```bash
# Reinstall client
pip uninstall dataops-client
pip install -e ~/Proj/streamflow-dataOps/streamflow-dataOps/dataops_client

# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +
```

### Issue: Cache Not Working

```bash
# Check cache database
sqlite3 data/dataops_cache.db ".tables"

# Clear cache
rm data/dataops_cache.db
python -c "from dataops_adapter.cache_manager import CacheManager; CacheManager('data/dataops_cache.db')"
```

---

## Resources

**Documentation:**
- [Integration Plan](./INTEGRATION_PLAN.md)
- [Architecture Comparison](./ARCHITECTURE_COMPARISON.md)
- [Integration Analysis](./INTEGRATION_ANALYSIS_SUMMARY.md)

**DataOps:**
- API Docs: http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/
- Dashboard: http://localhost:8000/streamflow/

**Code:**
- Dashboard: `~/Proj/streamflow-dashboard/usgs-streamflow-dashboard/`
- DataOps: `~/Proj/streamflow-dataOps/streamflow-dataOps/`
- Client: `~/Proj/streamflow-dataOps/streamflow-dataOps/dataops_client/`

---

## Daily Standup Template

**What I did yesterday:**
- Phase X: [specific tasks]
- Tests passing: X/Y
- Issues: [list any blockers]

**What I'm doing today:**
- Phase X: [planned tasks]
- Expected completion: [time]

**Blockers:**
- [List any blockers or questions]

---

## Completion Checklist

Phase 0: Preparation
- [ ] Backup created
- [ ] Client installed
- [ ] Environment configured
- [ ] Archive structure created

Phase 1: Adapter Layer
- [ ] Package structure created
- [ ] Client adapter implemented
- [ ] Cache manager implemented
- [ ] Tests written and passing

Phase 2: Data Manager
- [ ] data_manager.py refactored
- [ ] All USGS API calls removed
- [ ] Integration tests passing

Phase 3: Archive
- [ ] Files moved to archive/
- [ ] Archive documented
- [ ] Imports updated

Phase 4: Admin
- [ ] New minimal admin created
- [ ] Old admin archived
- [ ] DataOps links added

Phase 5: Testing
- [ ] Unit tests passing (>80%)
- [ ] Integration tests passing
- [ ] Performance acceptable
- [ ] Data validated

Phase 6: Deployment
- [ ] API mode enabled
- [ ] Production deployed
- [ ] Monitoring active
- [ ] Documentation updated

---

**Good luck with the migration! Follow the plan, test thoroughly, and don't hesitate to rollback if needed.**
