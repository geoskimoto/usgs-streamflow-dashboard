# Configurable USGS Station Data Collection Implementation

## Project Overview
Transform the current hardcoded station data collection system into a flexible, admin-configurable system using our refined NOAA HADS station lists. This will enable dynamic station selection, multiple collection profiles, and robust data management.

## Available Station Datasets
- **Pacific Northwest Full (1,506 stations)**: Complete regional coverage across 6 states
- **Columbia Basin HUC17 (563 stations)**: Focused watershed management dataset  
- **Custom Subsets**: Admin-defined collections based on geography, HUC codes, or specific needs

---

# PHASE 1: Database Schema for Site Configuration

## Objectives
Create a flexible database structure to manage station configurations, collection profiles, and operational metadata.

## Database Tables Design

### 1. `station_lists` - Master Station Registry
```sql
CREATE TABLE station_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usgs_id TEXT UNIQUE NOT NULL,
    nws_id TEXT,
    goes_id TEXT,
    station_name TEXT NOT NULL,
    state TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    huc_code TEXT,
    drainage_area REAL,
    source_dataset TEXT NOT NULL, -- 'HADS_PNW', 'HADS_Columbia', 'Custom'
    is_active BOOLEAN DEFAULT TRUE,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP
);
```

### 2. `station_configurations` - Collection Profiles
```sql
CREATE TABLE station_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT UNIQUE NOT NULL,
    description TEXT,
    station_count INTEGER,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. `configuration_stations` - Many-to-Many Relationship
```sql
CREATE TABLE configuration_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER REFERENCES station_configurations(id),
    station_id INTEGER REFERENCES station_lists(id),
    priority INTEGER DEFAULT 1, -- For processing order
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. `update_schedules` - Collection Job Management
```sql
CREATE TABLE update_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER REFERENCES station_configurations(id),
    schedule_name TEXT NOT NULL,
    data_type TEXT NOT NULL, -- 'realtime', 'daily', 'both'
    cron_expression TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. `data_collection_logs` - Operational History
```sql
CREATE TABLE data_collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER REFERENCES station_configurations(id),
    data_type TEXT NOT NULL,
    stations_attempted INTEGER,
    stations_successful INTEGER,
    stations_failed INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    error_summary TEXT,
    status TEXT NOT NULL -- 'running', 'completed', 'failed', 'cancelled'
);
```

## Implementation Tasks
1. **Database Migration Script**: Create tables with proper indexes and constraints
2. **Data Population**: Import HADS station lists into `station_lists` table
3. **Default Configurations**: Create initial profiles (PNW Full, Columbia Basin)
4. **Data Access Layer**: Build Python classes for database operations

---

# PHASE 2: Admin Interface for Station Management

## Objectives
Build a web-based administrative interface for managing station configurations, monitoring collection status, and controlling data collection jobs.

## Admin Interface Components

### 1. Station List Management
- **View All Stations**: Paginated table with search/filter capabilities
- **Station Details**: Individual station information with metadata
- **Bulk Operations**: Enable/disable multiple stations, batch updates
- **Import/Export**: CSV upload for custom station lists

### 2. Configuration Management
- **Configuration Overview**: List all collection profiles with stats
- **Create/Edit Profiles**: Drag-and-drop station selection interface
- **Geographic Selection**: Map-based station selection tool
- **HUC-Based Filtering**: Select stations by hydrologic unit codes

### 3. Schedule Management  
- **Job Scheduler**: Configure cron expressions for data collection
- **Schedule Templates**: Predefined schedules (hourly, daily, weekly)
- **Job Monitoring**: Real-time status of running collections
- **Performance Metrics**: Collection success rates, timing statistics

### 4. System Monitoring
- **Dashboard Overview**: System health, recent activity, error rates
- **Collection History**: Detailed logs with filtering and search
- **Alert Management**: Email/notification settings for failures
- **Database Statistics**: Storage usage, performance metrics

## User Interface Design
- **Framework**: Extend existing Dash/Plotly dashboard
- **Authentication**: Integrate with current admin authentication
- **Responsive Design**: Mobile-friendly interface for monitoring
- **Real-time Updates**: WebSocket connections for live status

## Implementation Tasks
1. **Route Structure**: Define admin URL patterns and navigation
2. **Authentication Middleware**: Secure admin-only access
3. **Database Integration**: Connect UI to configuration database
4. **Interactive Components**: Build station selection and scheduling UIs
5. **Status Monitoring**: Real-time job status and progress bars

---

# PHASE 3: Configurable Update Scripts

## Objectives
Modify existing data collection scripts to use database-driven station configurations instead of hardcoded CSV files.

## Script Modifications

### 1. Configuration Loading System
```python
class StationConfigManager:
    def get_active_configuration(self, config_name=None):
        """Load station list from database configuration"""
    
    def get_stations_for_config(self, config_id):
        """Retrieve stations for specific configuration"""
    
    def update_collection_status(self, config_id, status, metrics):
        """Log collection results to database"""
```

### 2. Enhanced Update Scripts

#### `update_realtime_discharge.py` Modifications
- **Dynamic Station Loading**: Query database for active configuration
- **Batch Processing**: Process stations in configurable chunks
- **Progress Tracking**: Real-time status updates to database
- **Error Handling**: Retry logic with exponential backoff
- **Rate Limiting**: Respect USGS API limits per configuration

#### `update_daily_discharge.py` Modifications  
- **Configuration Selection**: Allow multiple daily update profiles
- **Historical Backfill**: Smart detection of missing data ranges
- **Parallel Processing**: Multi-threaded collection with thread limits
- **Data Validation**: Quality checks before database insertion

### 3. Unified Collection Framework
```python
class DataCollectionEngine:
    def __init__(self, config_id):
        self.config = StationConfigManager().get_configuration(config_id)
        self.logger = CollectionLogger(config_id)
    
    def execute_collection(self, data_type='realtime'):
        """Main collection orchestration"""
    
    def process_station_batch(self, stations, batch_size=50):
        """Process stations in manageable batches"""
    
    def handle_collection_errors(self, station_id, error):
        """Centralized error handling and logging"""
```

## Implementation Tasks
1. **Database Integration**: Replace CSV reading with database queries
2. **Configuration APIs**: Build classes for station configuration management  
3. **Logging Enhancement**: Detailed progress and error tracking
4. **Script Refactoring**: Modularize collection logic for reusability
5. **Testing Framework**: Unit tests for configuration-driven collection

---

# PHASE 4: Batch Processing & Progress Tracking

## Objectives
Implement robust, scalable data collection with comprehensive monitoring, error handling, and performance optimization.

## Batch Processing Features

### 1. Intelligent Batch Management
- **Adaptive Batch Sizing**: Dynamic batch sizes based on API performance
- **Priority Queues**: Process high-priority stations first
- **Load Balancing**: Distribute requests across multiple API endpoints
- **Circuit Breaker**: Automatic fallback when services are degraded

### 2. Progress Monitoring System
```python
class CollectionProgressTracker:
    def start_collection(self, config_id, total_stations):
        """Initialize progress tracking"""
    
    def update_progress(self, completed, failed, current_station):
        """Real-time progress updates"""
    
    def estimate_completion(self):
        """Calculate ETA based on current performance"""
    
    def generate_progress_report(self):
        """Detailed status for admin interface"""
```

### 3. Advanced Error Handling
- **Retry Strategies**: Exponential backoff, jittered delays
- **Error Classification**: Temporary vs permanent failures
- **Fallback Data Sources**: Alternative APIs when primary fails
- **Partial Success Handling**: Save successful data even if batch fails

### 4. Performance Optimization
- **Connection Pooling**: Reuse HTTP connections for efficiency
- **Caching Layer**: Redis for frequently accessed station metadata
- **Asynchronous Processing**: Parallel data collection where possible
- **Memory Management**: Efficient handling of large datasets

## Monitoring & Alerting

### 1. Real-time Status Dashboard
- **Live Progress Bars**: Collection completion percentages
- **Performance Metrics**: Requests/second, success rates, response times
- **Error Visualization**: Heat maps of failure patterns
- **Resource Usage**: CPU, memory, network utilization

### 2. Alerting System
```python
class CollectionAlerts:
    def check_collection_health(self, config_id):
        """Monitor collection performance"""
    
    def send_failure_alert(self, error_details):
        """Email/SMS notifications for critical failures"""
    
    def generate_daily_report(self):
        """Automated summary reports"""
```

## Implementation Tasks
1. **Queue Management**: Redis-based job queues for batch processing
2. **Progress APIs**: WebSocket endpoints for real-time status
3. **Performance Monitoring**: Metrics collection and analysis
4. **Alert Configuration**: Email/SMS notification setup
5. **Optimization Testing**: Performance tuning and load testing

---

# INTEGRATION TESTING & DOCUMENTATION

## Testing Strategy
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: End-to-end collection workflows  
3. **Performance Tests**: Large-scale collection simulation
4. **User Acceptance**: Admin interface usability testing

## Documentation Requirements
1. **Admin User Guide**: Step-by-step interface operations
2. **API Documentation**: Developer reference for extensions
3. **Deployment Guide**: Production setup and configuration
4. **Troubleshooting**: Common issues and solutions

---

# SUCCESS METRICS

## Technical Metrics
- **Collection Reliability**: >99% success rate for active stations
- **Performance**: <30 seconds per 100 stations (realtime data)
- **Admin Efficiency**: Station configuration changes in <5 minutes
- **System Uptime**: >99.5% availability for data collection

## Operational Metrics  
- **Configuration Flexibility**: Support 5+ different station profiles
- **Monitoring Coverage**: Real-time status for all collection jobs
- **Error Recovery**: Automatic retry success rate >90%
- **User Satisfaction**: Admin interface ease-of-use rating >4.5/5

This comprehensive implementation will transform the static station system into a dynamic, scalable, and maintainable data collection platform suitable for diverse USGS streamflow monitoring needs.