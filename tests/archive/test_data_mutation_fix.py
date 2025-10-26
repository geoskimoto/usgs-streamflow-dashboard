#!/usr/bin/env python3
"""
Test data corruption at different stages of processing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_data_corruption_stages():
    """Test where data corruption occurs in the pipeline"""
    print("Testing Data Corruption Stages")
    print("=" * 45)
    
    try:
        # Test 1: Raw USGS API call
        print("🔬 Stage 1: Testing raw USGS API call...")
        
        import dataretrieval.nwis as nwis
        import pandas as pd
        
        # Use a known site
        site_id = "10092700"  # Bear River near Randolph, Utah
        start_date = "2024-10-01"
        end_date = "2024-10-21"
        
        print(f"   Fetching data for {site_id} from {start_date} to {end_date}")
        
        result = nwis.get_record(
            sites=site_id,
            service='dv', 
            start=start_date,
            end=end_date,
            parameterCd='00060'
        )
        
        # Handle result format
        if isinstance(result, tuple):
            raw_df, metadata = result
        else:
            raw_df = result
            
        print(f"   ✅ Got {len(raw_df)} records from USGS")
        print(f"   Raw index type: {type(raw_df.index)}")
        print(f"   Raw index sample: {raw_df.index[:3].tolist()}")
        
        if isinstance(raw_df.index, pd.DatetimeIndex):
            print(f"   Raw date range: {raw_df.index.min()} to {raw_df.index.max()}")
            
        print(f"   Raw columns: {list(raw_df.columns)}")
        print(f"   Raw data sample:")
        print(raw_df.head(3))
        
        # Test 2: After processing
        print(f"\n� Stage 2: Testing after _process_streamflow_dataframe...")
        
        from usgs_dashboard.data.data_manager import USGSDataManager
        dm = USGSDataManager()
        
        processed_df = dm._process_streamflow_dataframe(raw_df)
        
        print(f"   ✅ Processed {len(processed_df)} records")
        print(f"   Processed index type: {type(processed_df.index)}")
        print(f"   Processed index sample: {processed_df.index[:3].tolist()}")
        
        if isinstance(processed_df.index, pd.DatetimeIndex):
            print(f"   Processed date range: {processed_df.index.min()} to {processed_df.index.max()}")
            unique_years = processed_df.index.year.nunique()
            print(f"   Processed unique years: {unique_years}")
            
            if unique_years == 1 and processed_df.index.year.min() == 1970:
                print(f"   ❌ CORRUPTION FOUND: Processing converted dates to 1970!")
            else:
                print(f"   ✅ Processing preserved proper dates")
                
        print(f"   Processed columns: {list(processed_df.columns)}")
        print(f"   Processed data sample:")
        print(processed_df.head(3))
        
    except Exception as e:
        print(f"❌ Error in stage testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_data_corruption_stages()