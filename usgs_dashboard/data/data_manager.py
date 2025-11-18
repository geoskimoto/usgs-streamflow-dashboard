"""
USGS Data Manager for streamflow dashboard
OPTIMIZED: Single-pass data loading system for improved performance
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import dataretrieval.nwis as nwis
from typing import Optional, Dict, Any, List
import json
import os

from ..utils.config import TARGET_STATES, CACHE_DURATION, MAX_YEARS_LOAD, GAUGE_COLORS, SUBSET_CONFIG


class USGSDataManager:
    """Manages USGS data retrieval and caching for the dashboard."""
    
    def __init__(self, cache_dir: str = "data"):
        """
        Initialize the data manager.
        
        Parameters:
        -----------
        cache_dir : str
            Directory to store cache database
        """
        self.cache_dir = cache_dir
        self.cache_db = os.path.join(cache_dir, 'usgs_data.db')  # Updated to unified database
        os.makedirs(cache_dir, exist_ok=True)
        self.setup_cache()
        
    def setup_cache(self):
        """
        Verify database exists and is accessible.
        
        NOTE: Schema creation is handled by initialize_database.py
        This method only checks connectivity to the unified database.
        If database doesn't exist, attempts to create it automatically.
        """
        # If database doesn't exist, try to initialize it
        if not os.path.exists(self.cache_db):
            print(f"⚠️  Database not found at {self.cache_db}")
            print(f"⚠️  Attempting to initialize database automatically...")
            
            try:
                # Try to run initialize_database.py
                import subprocess
                result = subprocess.run(
                    ['python', 'initialize_database.py', '--db-path', self.cache_db],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    print(f"❌ Failed to initialize database: {result.stderr}")
                    raise RuntimeError(
                        f"Database not found and auto-initialization failed. "
                        f"Please run manually: python initialize_database.py --db-path {self.cache_db}"
                    )
                else:
                    print(f"✅ Database initialized successfully")
                    
            except Exception as e:
                print(f"❌ Error during auto-initialization: {e}")
                raise FileNotFoundError(
                    f"Database not found at {self.cache_db} and could not be created automatically. "
                    f"Please run: python initialize_database.py --db-path {self.cache_db}"
                )
        
        # Verify we can connect and that required tables exist
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            
            # Check for required tables from unified schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            required_tables = {'stations', 'streamflow_data', 'realtime_discharge'}
            missing_tables = required_tables - tables
            
            if missing_tables:
                conn.close()
                print(f"⚠️  Database missing required tables: {missing_tables}")
                raise RuntimeError(
                    f"Database is missing required tables: {missing_tables}. "
                    f"Please run: python initialize_database.py --db-path {self.cache_db} --force"
                )
            
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Database connection error: {e}")
    
    def load_regional_gauges(self, refresh=False, max_sites=None):
        """
        Load all USGS gauges for OR, WA, ID with metadata.
        OPTIMIZED: Single-pass data validation and download system.
        Only includes sites with discharge (00060) or gage height (00065) data (actual records).
        
        Parameters:
        -----------
        refresh : bool
            Force refresh of cached data
        max_sites : int, optional
            Maximum number of sites to load (overrides SUBSET_CONFIG)
        """
        if not refresh:
            cached_gauges = self._load_cached_gauge_metadata()
            if cached_gauges is not None and len(cached_gauges) > 0:
                print(f"Loaded {len(cached_gauges)} gauges from cache")
                return cached_gauges
        
        print("🚀 OPTIMIZED: Single-pass data loading system")
        print("Fetching gauge metadata from USGS...")
        
        # Step 1: Get basic site metadata (fast, no data downloads)
        all_gauges = self._fetch_basic_site_metadata()
        print(f"Total candidate gauges from USGS: {len(all_gauges)}")
        
        # Step 2: Apply subset EARLY if enabled (major optimization!)
        candidate_gauges = all_gauges
        if SUBSET_CONFIG['enabled']:
            candidate_gauges = self._apply_data_subset(all_gauges, max_sites)
            effective_max = max_sites if max_sites else SUBSET_CONFIG['max_sites']
            print(f"🎯 SUBSET APPLIED EARLY: Checking {len(candidate_gauges)} sites instead of {len(all_gauges)} (max_sites: {effective_max}, saved {len(all_gauges) - len(candidate_gauges)} API calls!)")
        
        # Step 3: Single-pass validation and data download
        print(f"🔍 Single-pass validation: downloading data for {len(candidate_gauges)} sites...")
        validated_gauges = self._validate_and_download_data(candidate_gauges)
        
        # Step 4: Process metadata and cache
        processed_gauges = self._process_gauge_metadata(validated_gauges)
        
        # Update stations table with enriched metadata (no additional data downloads needed)
        self._update_filters_table_optimized(processed_gauges)
        
        self._cache_gauge_metadata(processed_gauges)
        
        print(f"✅ Successfully loaded {len(processed_gauges)} gauges with validated data")
        print(f"🚀 Performance improvement: Single-pass system vs old two-pass system")
        return processed_gauges

    def _fetch_basic_site_metadata(self):
        """
        Fetch basic site metadata from USGS without any data downloads.
        Fast operation to get candidate sites.
        """
        all_gauges = []
        for state in TARGET_STATES:
            try:
                print(f"Fetching basic metadata for {state}...")
                gauges = nwis.get_record(
                    stateCd=state,
                    service='site',
                    parameterCd='00060,00065',
                    hasDataTypeCd='dv',
                    siteStatus='all'
                )
                if not gauges.empty:
                    gauges['state'] = state
                    all_gauges.append(gauges)
                    print(f"Found {len(gauges)} candidate gauges in {state}")
            except Exception as e:
                print(f"Error fetching metadata for {state}: {e}")
                continue
        
        if not all_gauges:
            raise ValueError("No gauges found for specified states")
        
        combined_gauges = pd.concat(all_gauges, ignore_index=True)
        return combined_gauges

    def _validate_and_download_data(self, candidate_gauges):
        """
        OPTIMIZED: Single-pass validation and data download.
        Attempts to download validation data for each site.
        If successful, site is valid and data is cached.
        If failed, site is excluded from final dataset.
        """
        validated_sites = []
        validation_years = SUBSET_CONFIG.get('validation_years', 2)
        
        for idx, gauge in candidate_gauges.iterrows():
            site_id = gauge.get('site_id')
            
            # Single operation: attempt data download for validation
            validation_data = self._download_validation_data(site_id, validation_years)
            
            if validation_data is not None and not validation_data.empty:
                # Site has valid data - add to validated list
                gauge_dict = gauge.to_dict()
                
                # Calculate metadata from the downloaded data
                if 'datetime' in validation_data.columns:
                    gauge_dict['last_data_date'] = validation_data['datetime'].max().strftime('%Y-%m-%d')
                    gauge_dict['data_years'] = len(validation_data['datetime'].dt.year.unique())
                    gauge_dict['has_recent_data'] = True
                    
                    # Check if data is recent (within last 60 days)
                    latest_date = validation_data['datetime'].max()
                    days_since_last = (datetime.now() - latest_date).days
                    gauge_dict['is_active'] = days_since_last <= 60
                else:
                    gauge_dict['has_recent_data'] = True
                    gauge_dict['is_active'] = True
                
                validated_sites.append(gauge_dict)
                print(f"✅ [{idx+1}/{len(candidate_gauges)}] Site {site_id} validated with {len(validation_data)} records")
            else:
                print(f"❌ [{idx+1}/{len(candidate_gauges)}] Site {site_id} has no valid data")
            
            # Progress reporting
            if (idx + 1) % 25 == 0 or idx == len(candidate_gauges) - 1:
                print(f"Progress: Validated {idx + 1}/{len(candidate_gauges)} sites, {len(validated_sites)} have data")
        
        print(f"🎯 Validation complete: {len(validated_sites)} sites with valid data out of {len(candidate_gauges)} checked")
        return pd.DataFrame(validated_sites)

    def _download_validation_data(self, site_id, validation_years=2):
        """
        Download recent data for validation (faster than full historical download).
        Returns processed data if site is active, None if no valid data.
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=validation_years*365)).strftime('%Y-%m-%d')
        
        # Try discharge first (00060), then gage height (00065)
        for param in ['00060', '00065']:
            try:
                result = nwis.get_record(
                    sites=site_id,
                    service='dv',
                    start=start_date,
                    end=end_date,
                    parameterCd=param
                )
                
                df = result[0] if isinstance(result, tuple) else result
                if df is not None and not df.empty and len(df) > 30:  # Require reasonable amount of data
                    processed_df = self._process_streamflow_dataframe(df)
                    
                    # Cache this data for future use
                    try:
                        self._cache_streamflow_data(site_id, processed_df, start_date, end_date)
                    except Exception as cache_error:
                        # Don't fail validation if caching fails
                        print(f"Warning: Could not cache data for {site_id}: {cache_error}")
                    
                    return processed_df
                    
            except Exception as e:
                # Try next parameter if this one fails
                continue
        
        return None  # No valid data found for either parameter

    def _update_filters_table_optimized(self, gauges_df):
        """
        OPTIMIZED: Update stations table with enriched metadata.
        No additional data downloads needed since data was downloaded during validation.
        """
        conn = sqlite3.connect(self.cache_db)
        
        for idx, gauge in gauges_df.iterrows():
            site_id = gauge.get('site_id')
            
            # Use metadata calculated during validation (no additional API calls!)
            num_water_years = gauge.get('data_years', 0)
            last_data_date = gauge.get('last_data_date', None)
            
            # Basin: use HUC code if available
            huc_code = gauge.get('huc_code', None) or gauge.get('huc_cd', None)
            basin = str(huc_code)[:4] if huc_code else None
            
            # Safe value conversion
            def safe_val(val):
                if pd.isna(val) or (hasattr(val, '__class__') and 'NaTType' in str(val.__class__)):
                    return None
                if hasattr(val, 'strftime'):
                    return val.strftime('%Y-%m-%d')
                if hasattr(val, 'item'):
                    return val.item()
                return val
            
            conn.execute('''
                INSERT OR REPLACE INTO stations (
                    site_id, station_name, latitude, longitude, drainage_area, state, county, site_type, agency, huc_code, basin, years_of_record, num_water_years, last_data_date, is_active, status, color, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_val(gauge.get('site_id')),
                safe_val(gauge.get('station_name')),
                safe_val(gauge.get('latitude')),
                safe_val(gauge.get('longitude')),
                safe_val(gauge.get('drainage_area')),
                safe_val(gauge.get('state')),
                safe_val(gauge.get('county')),
                safe_val(gauge.get('site_type')),
                safe_val(gauge.get('agency', 'USGS')),
                safe_val(huc_code),
                safe_val(basin),
                safe_val(gauge.get('years_of_record')),
                safe_val(num_water_years),
                safe_val(last_data_date),
                int(gauge.get('is_active', False)),
                safe_val(gauge.get('status')),
                safe_val(gauge.get('color')),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Updated stations table for {len(gauges_df)} sites (optimized - no additional API calls)")

    def _update_filters_table(self, gauges_df):
        """
        DEPRECATED: Old method with redundant data downloads.
        Kept for backward compatibility but should not be used in optimized flow.
        """
        print("⚠️  WARNING: Using deprecated _update_filters_table method")
        print("⚠️  Consider using _update_filters_table_optimized instead")
        
        # For now, just call the optimized version
        self._update_filters_table_optimized(gauges_df)

    def _update_filters_table(self, gauges_df):
        """
        Calculate and store comprehensive metadata for each site in the 'filters' table.
        Includes: number of water years, last data date, site type, drainage area, state, basin, etc.
        """
        import numpy as np
        conn = sqlite3.connect(self.cache_db)
        for idx, gauge in gauges_df.iterrows():
            site_id = gauge.get('site_id')
            # Try to get streamflow data for this site (for water years, last date)
            try:
                sf_df = self.get_streamflow_data(site_id, use_cache=True)
                if sf_df is not None and not sf_df.empty:
                    # Number of water years
                    if 'datetime' in sf_df.columns:
                        wy_years = sf_df['datetime'].dt.year.unique()
                        num_water_years = len(wy_years)
                        last_data_date = sf_df['datetime'].max().strftime('%Y-%m-%d')
                    else:
                        num_water_years = 0
                        last_data_date = None
                else:
                    num_water_years = 0
                    last_data_date = None
            except Exception as e:
                print(f"[filters] Error getting streamflow data for {site_id}: {e}")
                num_water_years = 0
                last_data_date = None
            # Basin: use HUC code if available
            huc_code = gauge.get('huc_code', None) or gauge.get('huc_cd', None)
            basin = str(huc_code)[:4] if huc_code else None
            # Compose insert/update
            def safe_val(val):
                if pd.isna(val) or (hasattr(val, '__class__') and 'NaTType' in str(val.__class__)):
                    return None
                if hasattr(val, 'strftime'):
                    return val.strftime('%Y-%m-%d')
                if hasattr(val, 'item'):
                    return val.item()
                return val
            conn.execute('''
                INSERT OR REPLACE INTO stations (
                    site_id, station_name, latitude, longitude, drainage_area, state, county, site_type, agency, huc_code, basin, years_of_record, num_water_years, last_data_date, is_active, status, color, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_val(gauge.get('site_id')),
                safe_val(gauge.get('station_name')),
                safe_val(gauge.get('latitude')),
                safe_val(gauge.get('longitude')),
                safe_val(gauge.get('drainage_area')),
                safe_val(gauge.get('state')),
                safe_val(gauge.get('county')),
                safe_val(gauge.get('site_type')),
                safe_val(gauge.get('agency', 'USGS')),
                safe_val(huc_code),
                safe_val(basin),
                safe_val(gauge.get('years_of_record')),
                safe_val(num_water_years),
                safe_val(last_data_date),
                int(gauge.get('is_active', False)),
                safe_val(gauge.get('status')),
                safe_val(gauge.get('color')),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()
    
    def _apply_data_subset(self, gauges_df: pd.DataFrame, max_sites: int = None) -> pd.DataFrame:
        """Apply data subset selection based on configuration."""
        if not SUBSET_CONFIG['enabled']:
            return gauges_df
        
        # Use provided max_sites or fall back to config
        if max_sites is None:
            max_sites = SUBSET_CONFIG['max_sites']
        if len(gauges_df) <= max_sites:
            print(f"Total sites ({len(gauges_df)}) is already <= subset size ({max_sites})")
            return gauges_df
        
        # Check if we have a cached subset selection
        if SUBSET_CONFIG['cache_subset_selection']:
            cached_subset = self._load_cached_subset(gauges_df)
            if cached_subset is not None:
                print(f"Using cached subset selection of {len(cached_subset)} sites")
                return cached_subset
        
        # Select subset based on method
        method = SUBSET_CONFIG['method']
        print(f"Selecting {max_sites} sites from {len(gauges_df)} using '{method}' method...")
        
        if method == 'balanced':
            subset_df = self._select_balanced_subset(gauges_df, max_sites)
        elif method == 'top_quality':
            subset_df = self._select_quality_subset(gauges_df, max_sites)
        else:  # random
            subset_df = self._select_random_subset(gauges_df, max_sites)
        
        # Cache the subset selection
        if SUBSET_CONFIG['cache_subset_selection']:
            self._cache_subset_selection(subset_df, len(gauges_df))
        
        return subset_df
    
    def _select_balanced_subset(self, gauges_df: pd.DataFrame, max_sites: int) -> pd.DataFrame:
        """Select a balanced subset across states and quality levels."""
        np.random.seed(SUBSET_CONFIG['selection_seed'])
        
        subset_sites = []
        state_dist = SUBSET_CONFIG['state_distribution']
        
        # Calculate target sites per state
        state_targets = {state: int(max_sites * ratio) for state, ratio in state_dist.items()}
        remaining = max_sites - sum(state_targets.values())
        
        # Distribute remaining sites
        if remaining > 0:
            states = list(state_targets.keys())
            for i in range(remaining):
                state_targets[states[i % len(states)]] += 1
        
        for state, target_count in state_targets.items():
            state_gauges = gauges_df[gauges_df['state'] == state].copy()
            
            if len(state_gauges) == 0:
                continue
            
            # For raw USGS data, we don't have 'is_active' yet - use simple random selection
            # Activity status will be determined during validation phase
            sample_size = min(target_count, len(state_gauges))
            selected = state_gauges.sample(n=sample_size, random_state=SUBSET_CONFIG['selection_seed'])
            subset_sites.extend(selected.index.tolist())
        
        subset_df = gauges_df.loc[subset_sites].copy()
        print(f"Balanced selection: {len(subset_df)} sites across states")
        return subset_df
    
    def _select_quality_subset(self, gauges_df: pd.DataFrame, max_sites: int) -> pd.DataFrame:
        """Select top quality sites (longest records, most recent data)."""
        # For raw USGS data, we don't have processed metadata yet
        # Use simple criteria available in raw data
        scored_gauges = gauges_df.copy()
        
        # Score based on drainage area if available (prefer moderate sizes)
        if 'drain_area_va' in scored_gauges.columns:
            da = pd.to_numeric(scored_gauges['drain_area_va'], errors='coerce').fillna(0)
            # Prefer drainage areas between 10 and 10,000 sq mi
            scored_gauges['da_score'] = np.where(
                (da >= 10) & (da <= 10000), 1.0,
                np.where(da > 0, 0.5, 0.0)
            )
        else:
            scored_gauges['da_score'] = 0.5
        
        # Score based on period of record if available
        if 'begin_date' in scored_gauges.columns and 'end_date' in scored_gauges.columns:
            try:
                begin_dates = pd.to_datetime(scored_gauges['begin_date'], errors='coerce')
                end_dates = pd.to_datetime(scored_gauges['end_date'], errors='coerce')
                years_of_record = (end_dates - begin_dates).dt.days / 365.25
                max_years = years_of_record.max()
                scored_gauges['years_score'] = years_of_record / max_years if max_years > 0 else 0.5
            except:
                scored_gauges['years_score'] = 0.5
        else:
            scored_gauges['years_score'] = 0.5
        
        # Combined quality score (simpler for raw data)
        scored_gauges['quality_score'] = (
            scored_gauges['years_score'] * 0.6 +
            scored_gauges['da_score'] * 0.4
        )
        
        # Select top sites
        top_sites = scored_gauges.nlargest(max_sites, 'quality_score')
        print(f"Quality selection: {len(top_sites)} highest-scoring sites")
        return top_sites.drop(columns=['years_score', 'da_score', 'quality_score'], errors='ignore')
    
    def _select_random_subset(self, gauges_df: pd.DataFrame, max_sites: int) -> pd.DataFrame:
        """Select random subset of sites."""
        np.random.seed(SUBSET_CONFIG['selection_seed'])
        
        subset_df = gauges_df.sample(n=max_sites, random_state=SUBSET_CONFIG['selection_seed'])
        print(f"Random selection: {len(subset_df)} sites")
        return subset_df
    
    def _cache_subset_selection(self, subset_df: pd.DataFrame, total_available: int):
        """Cache the subset selection for future use."""
        try:
            conn = sqlite3.connect(self.cache_db)
            
            # Clear old subset cache
            conn.execute("DELETE FROM subset_cache")
            
            # Store new subset
            site_ids = subset_df['site_id'].tolist()
            config_str = json.dumps(SUBSET_CONFIG)
            
            conn.execute('''
                INSERT INTO subset_cache (subset_config, site_ids, total_available, subset_size)
                VALUES (?, ?, ?, ?)
            ''', (config_str, json.dumps(site_ids), total_available, len(subset_df)))
            
            conn.commit()
            conn.close()
            print(f"Cached subset selection: {len(subset_df)} sites")
            
        except Exception as e:
            print(f"Error caching subset selection: {e}")
    
    def _load_cached_subset(self, gauges_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Load cached subset selection if valid."""
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT subset_config, site_ids, selection_date, total_available, subset_size
                FROM subset_cache
                ORDER BY selection_date DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return None
            
            config_str, site_ids_str, selection_date, total_available, subset_size = result
            
            # Check if configuration matches
            cached_config = json.loads(config_str)
            current_config = SUBSET_CONFIG.copy()
            
            # Compare relevant config keys
            config_keys = ['max_sites', 'method', 'prefer_active', 'state_distribution', 'selection_seed']
            for key in config_keys:
                if cached_config.get(key) != current_config.get(key):
                    print(f"Subset config changed ({key}), invalidating cache")
                    return None
            
            # Check if data size changed significantly
            if abs(total_available - len(gauges_df)) > 50:  # Allow small changes
                print(f"Data size changed significantly ({total_available} -> {len(gauges_df)}), invalidating cache")
                return None
            
            # Check cache age (invalidate after 7 days)
            cache_date = datetime.fromisoformat(selection_date)
            if (datetime.now() - cache_date).days > 7:
                print("Subset cache is older than 7 days, invalidating")
                return None
            
            # Load the subset
            site_ids = json.loads(site_ids_str)
            available_sites = set(gauges_df['site_id'].tolist())
            valid_site_ids = [sid for sid in site_ids if sid in available_sites]
            
            if len(valid_site_ids) < len(site_ids) * 0.9:  # If we lost >10% of sites
                print(f"Too many sites missing from cache ({len(valid_site_ids)}/{len(site_ids)}), invalidating")
                return None
            
            subset_df = gauges_df[gauges_df['site_id'].isin(valid_site_ids)].copy()
            return subset_df
            
        except Exception as e:
            print(f"Error loading cached subset: {e}")
            return None
    
    def _process_gauge_metadata(self, gauges_df):
        """Process gauge metadata and add calculated fields."""
        try:
            if not hasattr(self, '_columns_logged'):
                print(f"Available columns: {gauges_df.columns.tolist()}")
                if len(gauges_df) > 0:
                    print(f"Sample row: {dict(list(gauges_df.iloc[0].items())[:10])}")
                self._columns_logged = True
            processed_gauges = []
            activity_sample_count = 0
            if isinstance(gauges_df, pd.DataFrame):
                gauges = gauges_df.to_dict(orient='records')
            else:
                gauges = gauges_df
            for idx, gauge in enumerate(gauges):
                try:
                    # Ensure 'site_id' is present for dashboard compatibility
                    if 'site_id' in gauge:
                        gauge['site_id'] = gauge['site_id']
                    # Ensure 'station_name' is present for dashboard compatibility
                    if 'station_nm' in gauge:
                        gauge['station_name'] = gauge['station_nm']
                    # Ensure 'drainage_area' is present for dashboard compatibility
                    if 'drain_area_va' in gauge:
                        gauge['drainage_area'] = gauge['drain_area_va']
                    # Ensure 'years_of_record' is present for dashboard compatibility
                    gauge['years_of_record'] = self._calculate_years_of_record(gauge)
                    lat = pd.to_numeric(gauge.get('dec_lat_va'), errors='coerce')
                    lon = pd.to_numeric(gauge.get('dec_long_va'), errors='coerce')
                    if pd.isna(lat) or pd.isna(lon):
                        continue
                    gauge_data = gauge.copy()
                    gauge_data['latitude'] = lat
                    gauge_data['longitude'] = lon
                    years = gauge_data.get('years_of_record', None)
                    if years is not None and years >= 1:
                        if years >= 20:
                            gauge_data['color'] = GAUGE_COLORS['excellent']['color']
                            gauge_data['status'] = 'active_excellent'
                        elif years >= 10:
                            gauge_data['color'] = GAUGE_COLORS['good']['color']
                            gauge_data['status'] = 'active_good'
                        elif years >= 5:
                            gauge_data['color'] = GAUGE_COLORS['fair']['color']
                            gauge_data['status'] = 'active_fair'
                        else:
                            gauge_data['color'] = GAUGE_COLORS['poor']['color']
                            gauge_data['status'] = 'active_poor'
                    else:
                        gauge_data['color'] = GAUGE_COLORS['inactive']['color']
                        gauge_data['status'] = 'inactive'
                    processed_gauges.append(gauge_data)
                except Exception as e:
                    print(f"[{idx+1}/{len(gauges_df)}] Error processing site {gauge.get('site_id', 'UNKNOWN')}: {e}")
                    continue
            print(f"Successfully processed {len(processed_gauges)} gauges with valid coordinates")
            print(f"Activity checked for {activity_sample_count} sample sites")
            return pd.DataFrame(processed_gauges)
        except Exception as e:
            print(f"Error in _process_gauge_metadata: {e}")
            return pd.DataFrame()
    
    def _determine_site_activity(self, site_id: str) -> Dict:
        """Determine if a site has data within the last water year."""
        try:
            # Query last water year of data availability
            end_date = datetime.now()
            
            # Calculate start of current water year (Oct 1)
            if end_date.month >= 10:  # Oct-Dec
                wy_start = datetime(end_date.year, 10, 1)
            else:  # Jan-Sep
                wy_start = datetime(end_date.year - 1, 10, 1)
            
            # Check for data within current water year
            result = nwis.get_record(
                sites=site_id, 
                service='dv', 
                start=wy_start.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                parameterCd='00060'  # Streamflow
            )
            
            # Handle different return formats
            if isinstance(result, tuple):
                data_df = result[0]
            else:
                data_df = result
            
            if data_df is None or data_df.empty:
                return {
                    'is_active': False, 
                    'last_data_date': None, 
                    'recent_record_count': 0
                }
            
            # Check if we have data within the current water year
            has_recent_data = len(data_df) > 0
            last_measurement = data_df.index[-1] if len(data_df) > 0 else None
            
            # Remove the 30-day check: only require any data in the water year
            return {
                'is_active': has_recent_data,
                'last_data_date': last_measurement,
                'recent_record_count': len(data_df)
            }
            
        except Exception as e:
            return {
                'is_active': False, 
                'last_data_date': None, 
                'recent_record_count': 0
            }
    
    def _categorize_site_type(self, site_type_code: str) -> str:
        """Categorize USGS site types into user-friendly categories."""
        categories = {
            'ST': 'Surface Water - Stream',
            'LK': 'Surface Water - Lake/Reservoir', 
            'GW': 'Groundwater - Well',
            'SP': 'Surface Water - Spring',
            'WE': 'Groundwater - Well',
            'ES': 'Surface Water - Estuary',
            'OC': 'Surface Water - Ocean',
            'AT': 'Meteorological',
            'GL': 'Surface Water - Glacier'
        }
        return categories.get(site_type_code, f'Other ({site_type_code})')
    
    def _calculate_years_of_record(self, row):
        """Calculate years of record for a gauge with enhanced error handling"""
        try:
            # Get date values, handling various column names
            begin_date = None
            end_date = None
            
            # Try different possible column names for dates
            begin_cols = ['begin_date', 'parm_start_dt', 'start_date', 'first_date']
            end_cols = ['end_date', 'parm_end_dt', 'end_date', 'last_date']
            
            for col in begin_cols:
                if col in row and not pd.isna(row[col]):
                    begin_date = row[col]
                    break
                    
            for col in end_cols:
                if col in row and not pd.isna(row[col]):
                    end_date = row[col]
                    break
            
            # If we can't find valid dates, return 0
            if begin_date is None or end_date is None:
                return 0
            
            # Convert to datetime and handle NaN values
            if pd.isna(begin_date) or pd.isna(end_date):
                return 0
                
            begin_dt = pd.to_datetime(begin_date, errors='coerce')
            end_dt = pd.to_datetime(end_date, errors='coerce')
            
            # Check if conversion was successful
            if pd.isna(begin_dt) or pd.isna(end_dt):
                return 0
                
            years = (end_dt - begin_dt).days / 365.25
            return max(0, int(years))
            
        except Exception as e:
            # Don't print error for each gauge - too verbose
            return 0
    
    def _determine_gauge_status(self, years_of_record: int) -> str:
        """Determine gauge status based on years of record."""
        if years_of_record >= 20:
            return 'excellent'
        elif years_of_record >= 10:
            return 'good'
        elif years_of_record >= 5:
            return 'fair'
        elif years_of_record > 0:
            return 'poor'
        else:
            return 'inactive'
    
    def _cache_gauge_metadata(self, gauges: pd.DataFrame):
        """Cache gauge metadata in SQLite database with all required columns."""
        conn = sqlite3.connect(self.cache_db)
        
        # Ensure table exists with ALL required columns for filtering
        conn.execute('''
            CREATE TABLE IF NOT EXISTS gauge_metadata_new (
                site_id TEXT PRIMARY KEY,
                station_name TEXT,
                latitude REAL,
                longitude REAL,
                drainage_area REAL,
                state TEXT,
                site_type TEXT,
                agency TEXT,
                years_of_record INTEGER,
                is_active INTEGER,
                status TEXT,
                color TEXT,
                county TEXT,
                huc_code TEXT,
                last_data_date TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Drop old table and rename new one
        conn.execute("DROP TABLE IF EXISTS gauge_metadata")
        conn.execute("ALTER TABLE gauge_metadata_new RENAME TO gauge_metadata")
        
        # Insert new data with all columns, handling null values properly
        for _, gauge in gauges.iterrows():
            # Handle null/NaT/Timestamp values for SQLite compatibility
            def safe_value(val):
                """Convert pandas null types and timestamps to SQLite-compatible values."""
                if pd.isna(val) or (hasattr(val, '__class__') and 'NaTType' in str(val.__class__)):
                    return None
                # Convert pandas Timestamp to string
                if hasattr(val, 'strftime'):  # Timestamp objects
                    return val.strftime('%Y-%m-%d %H:%M:%S') if val is not None else None
                # Convert numpy/pandas types to native Python types
                if hasattr(val, 'item'):  # numpy types
                    return val.item()
                return val
            
            conn.execute('''
                INSERT OR REPLACE INTO gauge_metadata 
                (site_id, station_name, latitude, longitude, drainage_area, 
                 state, site_type, agency, years_of_record, is_active, status, 
                 color, county, huc_code, last_data_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_value(gauge['site_id']), safe_value(gauge['station_name']), 
                safe_value(gauge['latitude']), safe_value(gauge['longitude']), safe_value(gauge['drainage_area']),
                safe_value(gauge.get('state', '')), safe_value(gauge.get('site_type', '')), safe_value(gauge.get('agency', 'USGS')),
                safe_value(gauge['years_of_record']), int(gauge.get('is_active', False)), safe_value(gauge['status']),
                safe_value(gauge.get('color', '')), safe_value(gauge.get('county', '')), safe_value(gauge.get('huc_code', '')),
                safe_value(gauge.get('last_data_date', ''))
            ))
        
        conn.commit()
        conn.close()
    
    def _load_cached_gauge_metadata(self) -> Optional[pd.DataFrame]:
        """Load gauge metadata from cache with all required columns."""
        if not os.path.exists(self.cache_db):
            return None
        
        try:
            conn = sqlite3.connect(self.cache_db)
            
            # Check if data is recent (within 7 days)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*), MAX(last_updated) 
                FROM gauge_metadata
            ''')
            count, last_updated = cursor.fetchone()
            
            if count == 0:
                conn.close()
                return None
            
            if last_updated:
                last_update_time = datetime.fromisoformat(last_updated)
                if (datetime.now() - last_update_time).days > 7:
                    conn.close()
                    return None
            
            # Load ALL the data with proper column mapping
            gauges = pd.read_sql_query('''
                SELECT site_id, station_name, latitude, longitude, drainage_area,
                       state, site_type, agency, years_of_record, 
                       CASE WHEN is_active = 1 THEN true ELSE false END as is_active,
                       status, color, county, huc_code, last_data_date
                FROM gauge_metadata
            ''', conn)
            
            # Convert is_active back to boolean
            gauges['is_active'] = gauges['is_active'].astype(bool)
            
            conn.close()
            return gauges
            
        except Exception as e:
            print(f"Error loading cached gauge metadata: {e}")
            # If there's an error (e.g., missing columns), return None to force refresh
            return None
    
    def get_streamflow_data(self, site_id: str, start_date: str = None, 
                          end_date: str = None, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Get streamflow data for a specific gauge.
        
        Parameters:
        -----------
        site_id : str
            USGS site ID
        start_date : str
            Start date (YYYY-MM-DD)
        end_date : str  
            End date (YYYY-MM-DD)
        use_cache : bool
            Whether to use cached data
            
        Returns:
        --------
        pd.DataFrame or None
            Streamflow data
        """
        # Set default dates if not provided
        if not start_date:
            start_date = "1910-10-01"  # Extended range to include historical data
        if not end_date:
            # End date should be current date, not end of current water year
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # Try cache first
        if use_cache:
            cached_data = self._load_cached_streamflow_data(site_id, start_date, end_date)
            if cached_data is not None:
                return cached_data
        
        # Fetch from USGS
        try:
            print(f"Fetching streamflow data for site {site_id} from {start_date} to {end_date}...")
            result = nwis.get_record(
                sites=site_id,
                service='dv',
                start=start_date,
                end=end_date,
                parameterCd='00060'
            )
            
            # Handle different return formats
            if isinstance(result, tuple) and len(result) == 2:
                df, metadata = result
            elif isinstance(result, pd.DataFrame):
                df = result
                metadata = None
            else:
                df = result
                metadata = None
            
            if df is None or df.empty:
                print(f"No data returned from USGS for site {site_id}")
                return None
            
            print(f"Retrieved {len(df)} records for site {site_id}")
            # Show a small sample of the data
            print(f"[SUCCESS] Downloaded data for site {site_id}. Sample:")
            print(df.head(3).to_string(index=False))
            
            # Ensure proper datetime handling
            df = self._process_streamflow_dataframe(df)
            
            if df.empty:
                print(f"No valid data after processing for site {site_id}")
                return None
            
            # Cache the data
            if use_cache:
                self._cache_streamflow_data(site_id, df, start_date, end_date)
            
            return df
            
        except Exception as e:
            print(f"Error fetching streamflow data for {site_id}: {e}")
            # Try a more recent date range if the full range fails
            if start_date == "1910-10-01":
                print(f"Trying with recent data for site {site_id}...")
                try:
                    recent_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                    return self.get_streamflow_data(site_id, recent_start, end_date, use_cache)
                except Exception as e2:
                    print(f"Failed to get recent data for {site_id}: {e2}")
            return None
    
    def _process_streamflow_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process streamflow dataframe to ensure proper datetime structure."""
        try:
            # Make a copy to avoid modifying original
            df_processed = df.copy()
            
            # If already has proper datetime index, just clean timezone and return
            if isinstance(df_processed.index, pd.DatetimeIndex):
                # Remove timezone info to avoid timezone mixing issues  
                if df_processed.index.tz is not None:
                    df_processed.index = df_processed.index.tz_localize(None)
                return df_processed
            
            # If not datetime index, try to convert
            try:
                df_processed.index = pd.to_datetime(df_processed.index)
                # Remove timezone info to avoid timezone mixing issues
                if df_processed.index.tz is not None:
                    df_processed.index = df_processed.index.tz_localize(None)
                return df_processed
            except:
                pass
            
            # Last resort: look for datetime columns in the data
            datetime_col = None
            for col in df_processed.columns:
                if any(term in col.lower() for term in ['date', 'time']):
                    datetime_col = col
                    break
            
            if datetime_col:
                df_processed[datetime_col] = pd.to_datetime(df_processed[datetime_col], errors='coerce')
                if df_processed[datetime_col].dt.tz is not None:
                    df_processed[datetime_col] = df_processed[datetime_col].dt.tz_localize(None)
                df_processed = df_processed.set_index(datetime_col)
                return df_processed
            
            # If we get here, we couldn't find proper datetime info
            print("Warning: Could not find proper datetime information in dataframe")
            return df_processed
            
        except Exception as e:
            print(f"Error processing streamflow dataframe: {e}")
            # Return original dataframe if processing fails
            return df
    
    def _load_cached_streamflow_data(self, site_id: str, start_date: str, 
                                   end_date: str) -> Optional[pd.DataFrame]:
        """Load cached streamflow data."""
        if not os.path.exists(self.cache_db):
            return None
        
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT data_json, last_updated 
                FROM streamflow_data 
                WHERE site_id = ? AND start_date = ? AND end_date = ?
            ''', (site_id, start_date, end_date))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return None
            
            data_json, last_updated = result
            
            # Check if data is stale
            last_update_time = datetime.fromisoformat(last_updated)
            if (datetime.now() - last_update_time).seconds > CACHE_DURATION:
                return None
            
            # Parse JSON data back to DataFrame
            data = json.loads(data_json)
            df = pd.DataFrame(data)
            
            # Convert datetime column back to DatetimeIndex
            if 'datetime' in df.columns:
                # Convert datetime string back to datetime objects
                df['datetime'] = pd.to_datetime(df['datetime'])
                # Remove timezone info to avoid timezone mixing issues
                if df['datetime'].dt.tz is not None:
                    df['datetime'] = df['datetime'].dt.tz_localize(None)
                # Set as index with proper name
                df = df.set_index('datetime')
                df.index.name = 'datetime'
            elif not isinstance(df.index, pd.DatetimeIndex):
                # Try to convert index to datetime if no datetime column found
                try:
                    df.index = pd.to_datetime(df.index, errors='coerce')
                    df.index.name = 'datetime'
                    # Remove timezone info from index if present
                    if hasattr(df.index, 'tz') and df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                except:
                    print(f"Warning: Could not convert index to datetime for site {site_id}")
            
            return df
            
        except Exception as e:
            print(f"Error loading cached streamflow data: {e}")
            return None
    
    def _cache_streamflow_data(self, site_id: str, df: pd.DataFrame, 
                             start_date: str, end_date: str):
        """Cache streamflow data."""
        try:
            conn = sqlite3.connect(self.cache_db)
            
            # Convert DataFrame to JSON, preserving datetime index
            df_copy = df.copy()
            
            # Reset index to make datetime a column for JSON serialization
            if isinstance(df_copy.index, pd.DatetimeIndex):
                df_copy = df_copy.reset_index()
                if 'datetime' in df_copy.columns:
                    df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                elif df_copy.index.name and 'datetime' in str(df_copy.index.name):
                    df_copy['datetime'] = df_copy.index.strftime('%Y-%m-%d %H:%M:%S')
            elif 'datetime' in df_copy.columns:
                df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            data_json = df_copy.to_json(orient='records')
            
            # Insert or replace data
            conn.execute('''
                INSERT OR REPLACE INTO streamflow_data 
                (site_id, data_json, start_date, end_date, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (site_id, data_json, start_date, end_date, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error caching streamflow data: {e}")
    
    def get_gauge_metadata(self, site_id: str) -> Dict:
        """Get comprehensive metadata for a specific gauge."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM gauge_metadata WHERE site_id = ?
        ''', (site_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {}
        
        # Convert to dictionary
        columns = ['site_id', 'station_name', 'latitude', 'longitude', 
                  'drainage_area', 'state_cd', 'begin_date', 'end_date', 
                  'years_of_record', 'status']
        
        metadata = dict(zip(columns, result[:-1]))  # Exclude last_updated
        return metadata
    
    def get_realtime_data(self, site_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Get high-resolution real-time data from the realtime_discharge table.
        
        Args:
            site_id: USGS site ID
            start_date: Start date in YYYY-MM-DD format (optional, defaults to 5 days ago)
            end_date: End date in YYYY-MM-DD format (optional, defaults to now)
            
        Returns:
            DataFrame with datetime index and discharge values
        """
        try:
            # Default to last 5 days if no dates specified
            if not start_date:
                start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(self.cache_db)
            
            query = '''
                SELECT datetime_utc, discharge_cfs, data_quality as qualifiers
                FROM realtime_discharge 
                WHERE site_id = ? 
                AND datetime_utc >= ? 
                AND datetime_utc <= ? 
                ORDER BY datetime_utc
            '''
            
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(site_id, start_date, end_date),
                parse_dates=['datetime_utc'],
                index_col='datetime_utc'
            )
            
            conn.close()
            
            if df.empty:
                print(f"No real-time data found for site {site_id} between {start_date} and {end_date}")
                return pd.DataFrame()
            
            # Clean up the data
            df = self._process_streamflow_dataframe(df)
            
            # Remove timezone info to match daily data format
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Rename columns to match daily data format
            if 'discharge_cfs' in df.columns:
                df = df.rename(columns={'discharge_cfs': 'discharge'})
            
            print(f"Retrieved {len(df)} real-time records for site {site_id}")
            return df
            
        except Exception as e:
            print(f"Error fetching real-time data for {site_id}: {e}")
            return pd.DataFrame()
    
    def get_sites_with_realtime_data(self) -> List[str]:
        """Get a list of site IDs that have real-time data available.
        
        Returns:
            List of site IDs that have data in the realtime_discharge table
        """
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT site_id 
                FROM realtime_discharge 
                ORDER BY site_id
            ''')
            
            sites = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            print(f"Found {len(sites)} sites with real-time data")
            return sites
            
        except Exception as e:
            print(f"Error getting sites with real-time data: {e}")
            return []
    
    def clear_cache(self):
        """Clear all cached data."""
        if os.path.exists(self.cache_db):
            conn = sqlite3.connect(self.cache_db)
            conn.execute("DELETE FROM gauge_metadata")
            conn.execute("DELETE FROM streamflow_data")
            conn.execute("DELETE FROM data_statistics")
            conn.execute("DELETE FROM subset_cache")
            conn.execute("DELETE FROM stations")
            conn.commit()
            conn.close()
            print("Cache cleared successfully")
    
    def get_subset_status(self) -> Dict:
        """Get information about current subset configuration and status."""
        status = {
            'enabled': SUBSET_CONFIG['enabled'],
            'max_sites': SUBSET_CONFIG['max_sites'],
            'method': SUBSET_CONFIG['method'],
            'has_cached_selection': False,
            'cache_date': None,
            'cached_size': 0
        }
        
        if not SUBSET_CONFIG['enabled']:
            return status
        
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT selection_date, subset_size
                FROM subset_cache
                ORDER BY selection_date DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                status['has_cached_selection'] = True
                status['cache_date'] = result[0]
                status['cached_size'] = result[1]
                
        except Exception as e:
            print(f"Error getting subset status: {e}")
        
        return status
    
    def filter_gauges_by_parameters(self, gauges_df: pd.DataFrame, selected_parameters: list) -> pd.DataFrame:
        """Filter gauges to only those with at least one of the selected parameters."""
        if 'available_parameters' not in gauges_df.columns:
            print("Warning: 'available_parameters' column missing from gauge metadata. Skipping parameter filter.")
            return gauges_df
        if not selected_parameters:
            return gauges_df
        mask = gauges_df['available_parameters'].apply(
            lambda params: any(p in params for p in selected_parameters) if isinstance(params, list) else False
        )
        return gauges_df[mask]
    
    def apply_advanced_filters(self, filters_df: pd.DataFrame, filter_criteria: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply advanced filtering to the filters table based on multiple criteria.
        
        Parameters:
        -----------
        filters_df : pd.DataFrame
            DataFrame from the filters table
        filter_criteria : Dict[str, Any]
            Dictionary containing filter criteria:
            - status: List of status values ('active', 'inactive')
            - states: List of state abbreviations 
            - drainage_range: Tuple of (min, max) drainage area
            - site_types: List of site type codes
            - agency: Agency code or 'ALL'
            - quality: List of quality requirements
            - years_range: Tuple of (min, max) years of record
        
        Returns:
        --------
        pd.DataFrame
            Filtered DataFrame
        """
        filtered_df = filters_df.copy()
        
        # Search filter (site_id or station_name)
        if 'search_text' in filter_criteria and filter_criteria['search_text']:
            search_text = filter_criteria['search_text'].lower().strip()
            if search_text:
                search_mask = (
                    filtered_df['site_id'].str.lower().str.contains(search_text, na=False) |
                    filtered_df['station_name'].str.lower().str.contains(search_text, na=False)
                )
                filtered_df = filtered_df[search_mask]


        
        # State filter
        if 'states' in filter_criteria and filter_criteria['states']:
            filtered_df = filtered_df[filtered_df['state'].isin(filter_criteria['states'])]
        
        # Drainage area filter
        if 'drainage_area_range' in filter_criteria and filter_criteria['drainage_area_range']:
            min_da, max_da = filter_criteria['drainage_area_range']
            # Handle null drainage areas
            mask = (
                (filtered_df['drainage_area'].notna()) &
                (filtered_df['drainage_area'] >= min_da) & 
                (filtered_df['drainage_area'] <= max_da)
            )
            # Include sites with no drainage area data if min is 0
            if min_da == 0:
                mask = mask | filtered_df['drainage_area'].isna()
            filtered_df = filtered_df[mask]
        
        # Basin filter
        if 'basins' in filter_criteria and filter_criteria['basins']:
            filtered_df = filtered_df[filtered_df['basin'].isin(filter_criteria['basins'])]
            
        # HUC code filter
        if 'huc_codes' in filter_criteria and filter_criteria['huc_codes']:
            filtered_df = filtered_df[filtered_df['huc_code'].isin(filter_criteria['huc_codes'])]
        
        return filtered_df
    
    def get_filter_statistics(self, filters_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get statistics about the current filter data for UI display.
        
        Parameters:
        -----------
        filters_df : pd.DataFrame
            DataFrame from the filters table
        
        Returns:
        --------
        Dict[str, Any]
            Dictionary containing statistics about the filtered data
        """
        stats = {}
        
        # Overall counts
        stats['total_sites'] = len(filters_df)
        stats['active_sites'] = len(filters_df[filters_df['is_active'] == 1])
        stats['inactive_sites'] = len(filters_df[filters_df['is_active'] == 0])
        
        # State distribution
        stats['states'] = filters_df['state'].value_counts().to_dict()
        
        # Site type distribution
        stats['site_types'] = filters_df['site_type'].value_counts().to_dict()
        
        # Drainage area statistics
        drainage_data = filters_df['drainage_area'].dropna()
        if len(drainage_data) > 0:
            stats['drainage_area'] = {
                'min': float(drainage_data.min()),
                'max': float(drainage_data.max()),
                'median': float(drainage_data.median()),
                'count_with_data': len(drainage_data)
            }
        else:
            stats['drainage_area'] = {'min': 0, 'max': 0, 'median': 0, 'count_with_data': 0}
        
        # Years of record statistics
        years_data = filters_df['years_of_record'].dropna()
        if len(years_data) > 0:
            stats['years_of_record'] = {
                'min': int(years_data.min()),
                'max': int(years_data.max()),
                'median': float(years_data.median()),
                'count_with_data': len(years_data)
            }
        else:
            stats['years_of_record'] = {'min': 0, 'max': 0, 'median': 0, 'count_with_data': 0}
        
        return stats
    
    def make_json_serializable(self, data):
        def fix_value(val):
            if isinstance(val, float) and (pd.isna(val) or np.isnan(val) or np.isinf(val)):
                return None
            if hasattr(val, 'item'):
                return val.item()
            if hasattr(val, 'to_dict'):
                return val.to_dict()
            if str(type(val)).startswith("<class 'shapely."):
                return str(val)
            return val
        return [{k: fix_value(v) for k, v in row.items()} for row in data]

    def get_filters_table(self) -> pd.DataFrame:
        """
        Get the filters table from the unified database with enriched metadata.
        
        Returns:
        --------
        pd.DataFrame
            DataFrame containing all station data with enriched metadata
            (drainage_area, years_of_record, etc.)
        """
        try:
            conn = sqlite3.connect(self.cache_db)
            # Load from unified stations table (contains both basic and enriched metadata)
            filters_df = pd.read_sql_query('SELECT * FROM stations', conn)
            
            conn.close()
            return filters_df
        except Exception as e:
            print(f"Error getting filters table: {e}")
            # Try stations table as fallback
            try:
                conn = sqlite3.connect(self.cache_db)
                filters_df = pd.read_sql_query('SELECT * FROM stations', conn)
                conn.close()
                return filters_df
            except:
                return pd.DataFrame()

    def get_available_counties(self, selected_states: List[str]) -> List[str]:
        """
        Get available counties for the selected states.
        
        Parameters:
        -----------
        selected_states : List[str]
            List of state abbreviations
        
        Returns:
        --------
        List[str]
            List of available county names
        """
        try:
            # Get the filters table
            filters_df = self.get_filters_table()
            
            # Filter by selected states and get unique counties
            state_filtered = filters_df[filters_df['state'].isin(selected_states)]
            counties = state_filtered['county'].dropna()
            counties = counties[counties != '']  # Remove empty strings
            
            return list(counties.unique())
            
        except Exception as e:
            print(f"Error getting available counties: {e}")
            return []


# Convenience function for initializing data manager
def get_data_manager() -> USGSDataManager:
    """Get initialized data manager instance."""
    return USGSDataManager()
