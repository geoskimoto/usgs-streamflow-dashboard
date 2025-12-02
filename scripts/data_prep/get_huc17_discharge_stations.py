#!/usr/bin/env python3
"""
Fetch all USGS streamflow stations in Pacific Northwest states (OR, WA, ID, MT, NV) 
that have discharge data (parameter 00060).

This creates a clean, pre-filtered list for efficient data processing, eliminating 
the need to ping 2800+ sites individually. Also identifies HUC 17 stations for 
default filtering in the dashboard.
"""

import requests
import pandas as pd
import json
from datetime import datetime
import time

def get_state_discharge_stations():
    """
    Fetch all USGS stations in Pacific Northwest states with discharge data (parameter 00060).
    
    States: OR (Oregon), WA (Washington), ID (Idaho), MT (Montana), NV (Nevada)
    
    Returns:
        pd.DataFrame: DataFrame with station information
    """
    print("🔍 Fetching Pacific Northwest discharge stations by state...")
    
    # Target states
    states = ['OR', 'WA', 'ID', 'MT', 'NV']
    all_stations = []
    
    # USGS Web Services URL for site information
    base_url = "https://waterservices.usgs.gov/nwis/site/"
    
    for state in states:
        print(f"\n📍 Processing {state}...")
        
        # Parameters for each state query
        params = {
            'format': 'json',
            'stateCd': state,  # State code
            'parameterCd': '00060',  # Discharge parameter
            'siteType': 'ST',  # Stream sites only
            'hasDataTypeCd': 'dv',  # Daily values
            'siteStatus': 'all'  # Include both active and inactive sites
        }