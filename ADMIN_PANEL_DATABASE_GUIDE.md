# USGS Streamflow Dashboard - Admin Panel & Database Management System

## System Architecture Overview

The admin panel is a sophisticated **multi-tier configuration management system** for managing USGS streamflow gauge data collection. It provides a web-based interface for configuring which stations to monitor, scheduling automated data updates, and tracking system performance.

---

## 🗄️ Database Structure

The system uses **SQLite databases** with the following architecture:

### Core Database: `data/station_config.db`

Contains 6 main tables and 3 views:

#### 📍 Tables:

1. **`station_lists`** - Master station registry
   - All USGS discharge monitoring stations (1,506 stations)
   - Station metadata: USGS ID, name, coordinates, drainage area, HUC codes
   - Source tracking: HADS_PNW (943 stations), HADS_Columbia (563 stations)
   - Active/inactive status flags

2. **`station_configurations`** - Collection profiles
   - Named groups of stations (e.g., "Pacific Northwest Full", "Columbia River Basin")
   - Default configuration marking
   - Metadata: description, creation date, station counts

3. **`configuration_stations`** - Many-to-many relationship table
   - Links configurations to stations
   - Priority ordering for processing
   - Audit trail (who added, when)

4. **`update_schedules`** - Automated collection jobs
   - Cron-style scheduling (e.g., "*/15 * * * *" for every 15 min)
   - Data type selection: realtime, daily, or both
   - Next run tracking and run counts

5. **`data_collection_logs`** - Operational history
   - Tracks each collection run
   - Success/failure metrics per run
   - Duration, error summaries, trigger source

6. **`station_collection_errors`** - Detailed error tracking
   - Individual station failures
   - Error types, HTTP status codes
   - Retry counts and timestamps

#### 📊 Views (pre-computed queries):

- **`configuration_summary`** - Configuration overview with counts
- **`stations_by_state`** - Geographic distribution
- **`recent_collection_activity`** - Last 100 collection runs

### Data Cache: `data/usgs_cache.db`

Stores actual streamflow measurements (real-time and daily data) - managed separately.

---

## 🎛️ Admin Panel Components

### Access Method:
1. Navigate to dashboard: `http://localhost:8050`
2. Click **🔧 Admin** tab
3. Login with credentials: `admin` / `admin123`
4. Access protected management functions

### Five Main Sections:

#### 1. 📈 Dashboard Tab (System Overview)
**Purpose:** Quick health check and system status

**Displays:**
- Active configurations count
- Total active stations
- 24-hour success rate percentage
- Currently running collection jobs
- Next scheduled runs
- Recent activity summary

**Use Case:** Quick morning check - "Is everything running smoothly?"

---

#### 2. 🎯 Configurations Tab (Station Configuration Management)
**Purpose:** Manage collections of stations

**Features:**
- **View Configurations:** Interactive table showing all configurations
  - Name, station count, active/inactive status
  - Default configuration marking (⭐)
  - Creation dates and descriptions
  
- **Default Configurations:**
  - **Pacific Northwest Full**: 1,506 stations (all HADS data)
  - **Columbia River Basin (HUC17)**: 563 stations (Columbia watershed only)
  - **Development Test Set**: 25 stations (for testing)

**Workflow:**
1. Admin views list of configurations
2. Clicks on configuration to see details
3. Can create new configurations by selecting station subsets
4. Sets one as default for main dashboard

---

#### 3. 🗺️ Stations Tab (Station Browser)
**Purpose:** Explore and filter the master station list

**Advanced Filtering:**
- **By State:** Multi-select (WA, OR, ID, MT, NV, CA)
- **By HUC Code:** Watershed filtering (e.g., "1701" for Columbia Basin)
- **By Source Dataset:** HADS_PNW vs HADS_Columbia
- **By Text Search:** Station name or USGS ID

**Display Information:**
- USGS ID, station name, state
- Latitude/longitude coordinates
- HUC code (watershed identifier)
- Drainage area (square miles)
- Source dataset

**Workflow:**
1. Admin needs to find stations in specific region
2. Filters by state = "WA" and HUC = "1701"
3. System shows matching stations (e.g., 250 results)
4. Admin can select stations to create new configuration

---

#### 4. ⏰ Schedules Tab (Automated Collection Management)
**Purpose:** Configure when and what data gets collected

**Features:**
- View all scheduled jobs
- Enable/disable schedules
- Create new schedules with cron expressions
- Track last run, next run, run counts

**Schedule Types:**
- **Realtime Data:** Every 15 minutes, 30 minutes, hourly
- **Daily Data:** Once per day (typically 6 AM)
- **Custom:** Any cron expression

**Example Schedules:**
```
Columbia Basin - Realtime (15min)  →  */15 * * * *  (every 15 minutes)
Columbia Basin - Daily (6 AM)      →  0 6 * * *     (daily at 6 AM)
PNW Full - Realtime (hourly)       →  0 * * * *     (every hour)
```

**Workflow:**
1. Admin creates new configuration
2. Navigates to Schedules tab
3. Clicks "➕ New Schedule"
4. Selects configuration, data type, frequency
5. System automatically runs at scheduled times

---

#### 5. 📊 Monitoring Tab (Collection Activity Tracking)
**Purpose:** Monitor system performance and troubleshoot issues

**Real-time Metrics:**
- **System Health:** Active configs, stations, success rates
- **24-Hour Statistics:** Collection runs, success/failure counts
- **Currently Running:** Active data collection jobs

**Activity Table:**
- Recent collection runs (last 10-100 runs)
- Status icons: ✅ Completed, ❌ Failed, 🔄 Running
- Configuration name, data type
- Success rate: "145/150 stations successful"
- Duration in minutes
- Timestamp and trigger source (manual vs scheduled)

**Error Tracking:**
- Drill down into failed collections
- See which specific stations failed
- Error types: network, data format, API issues
- HTTP status codes

**Workflow:**
1. Admin notices success rate dropped to 85%
2. Opens Monitoring tab
3. Sees recent run had 20 failed stations
4. Clicks on failed run to see error details
5. Identifies stations with network timeouts
6. Can manually re-run or mark stations inactive

---

## 🔄 How the System Works

### Data Flow:

```
┌─────────────────────────────────────────────────────────┐
│  1. CONFIGURATION SETUP (Admin Panel)                   │
│     - Admin creates "Columbia Basin" configuration       │
│     - Selects 563 stations from master list             │
│     - Creates schedule: "Every 15 minutes, realtime"   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  2. SCHEDULED EXECUTION (Cron/Smart Scheduler)          │
│     - Scheduler checks next_run times                   │
│     - Triggers collection script at scheduled time      │
│     - Creates log entry with "running" status           │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  3. DATA COLLECTION (Update Scripts)                    │
│     - Script queries config DB for station list         │
│     - Loops through 563 stations                        │
│     - Fetches data from USGS API for each              │
│     - Writes to usgs_cache.db                          │
│     - Logs errors for failed stations                   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  4. RESULT LOGGING (Database Updates)                   │
│     - Updates collection log: "completed"               │
│     - Records: 558 successful, 5 failed                 │
│     - Stores duration: 12.3 minutes                     │
│     - Updates next_run time for schedule                │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  5. MONITORING & VISUALIZATION (Admin Panel)            │
│     - Dashboard shows success rate: 99.1%               │
│     - Recent activity table updates                     │
│     - Main dashboard displays updated streamflow data   │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Use Cases

### Use Case 1: Creating a Custom Region Configuration
**Scenario:** You want to monitor only Washington state stations

1. **Navigate:** Admin → Stations Tab
2. **Filter:** State = "WA"
3. **Review:** System shows ~300 WA stations
4. **Select:** Click stations or "Select All"
5. **Create:** Click "Create Configuration from Selection"
6. **Name:** "Washington State Only"
7. **Schedule:** Set realtime collection every 30 minutes
8. **Result:** New configuration appears in dashboard dropdown

### Use Case 2: Troubleshooting Failed Collections
**Scenario:** Dashboard shows old data, something is wrong

1. **Check:** Admin → Dashboard → System Health
2. **Notice:** Success rate dropped to 60%
3. **Investigate:** Monitoring Tab → Recent Activity
4. **Find:** Last 3 runs failed with "HTTP 503 errors"
5. **Diagnose:** USGS API experiencing issues
6. **Action:** Temporarily disable schedule, wait for API recovery
7. **Follow-up:** Re-enable schedule, verify success rate returns to 99%+

### Use Case 3: Setting Up a New Production System
**Scenario:** Deploying to a new server

1. **Initialize Database:** Run `python setup_configuration_database.py`
2. **Populate Stations:** Run `python populate_station_database.py`
3. **Verify:** Admin panel shows 1,506 stations, 3 configurations
4. **Configure Schedules:** Adjust cron expressions for production timing
5. **Test:** Manual trigger one collection, verify success
6. **Deploy:** Enable all schedules, monitor first 24 hours

---

## 🔒 Security & Authentication

- **Public Dashboard:** No login required (read-only access to gauges)
- **Admin Panel:** Protected by username/password
- **Default Credentials:** `admin` / `admin123` (should change in production)
- **Session-based:** Uses Flask-Login for session management
- **Environment Override:** Set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` env vars
- **Password Hashing:** SHA-256 for credential storage

---

## 📊 Statistics & Monitoring

The system automatically tracks:
- **Collection Success Rates:** Per configuration and overall
- **Station Reliability:** Which stations frequently fail
- **Performance Metrics:** Average collection duration
- **Error Patterns:** Most common error types
- **API Health:** HTTP status code tracking
- **Historical Trends:** 7-day, 30-day statistics

---

## 🚀 Benefits of This System

1. **Flexibility:** Switch between full PNW dataset or Columbia Basin subset
2. **Reliability:** Automated scheduling with error tracking and retry logic
3. **Visibility:** Real-time monitoring of collection health
4. **Scalability:** Easy to add new configurations or stations
5. **Maintainability:** Centralized management through web interface
6. **Audit Trail:** Complete history of all collection operations

---

## 🛠️ Setup Instructions

### Initial Setup (First Time)

1. **Create the configuration database:**
   ```bash
   python setup_configuration_database.py
   ```
   This creates `data/station_config.db` with all tables and views.

2. **Populate with station data:**
   ```bash
   python populate_station_database.py
   ```
   This loads 1,506 stations from CSV files and creates default configurations.

3. **Verify database:**
   ```bash
   sqlite3 data/station_config.db "SELECT * FROM configuration_summary;"
   ```

4. **Start the dashboard:**
   ```bash
   python app.py
   ```

5. **Access admin panel:**
   - Open http://localhost:8050
   - Click "🔧 Admin" tab
   - Login: `admin` / `admin123`

### Troubleshooting

**Error: "Configuration database not found"**
- The database hasn't been created yet
- Run: `python setup_configuration_database.py`
- Then run: `python populate_station_database.py`

**Error: "No configurations found"**
- Database exists but is empty
- Run: `python populate_station_database.py`

**Error: "No default configuration found"**
- Configurations exist but none marked as default
- Use admin panel to set a default configuration
- Or update database: `UPDATE station_configurations SET is_default = 1 WHERE config_name = 'Pacific Northwest Full'`

---

This is a **production-ready, enterprise-level data collection management system** that allows you to configure, monitor, and maintain automated USGS streamflow data collection at scale. The admin panel gives you complete visibility and control over the entire data pipeline.
