#!/usr/bin/env python3
"""
One-Command Deployment Script

Handles complete deployment setup:
1. Initializes database schema
2. Imports all station datasets
3. Optionally pre-populates data
4. Starts the dashboard

Usage:
    python deploy.py                    # Full setup + start dashboard
    python deploy.py --skip-data        # Skip data pre-population
    python deploy.py --setup-only       # Setup only, don't start dashboard
    python deploy.py --quick            # Just start dashboard (no setup)
"""

import sys
import os
from pathlib import Path
import subprocess
import argparse
from datetime import datetime

# Color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_step(number, text):
    """Print a step number and description."""
    print(f"{Colors.BOLD}{Colors.OKCYAN}[{number}] {text}{Colors.ENDC}")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ️  {text}{Colors.ENDC}")


def check_dependencies():
    """Check if required dependencies are installed."""
    print_step("0", "Checking dependencies")
    
    try:
        import pandas
        import numpy
        import dash
        import plotly
        print_success("All Python dependencies installed")
        return True
    except ImportError as e:
        print_error(f"Missing dependencies: {e}")
        print_info("Run: pip install -r requirements.txt")
        return False


def initialize_database():
    """Initialize database schema."""
    print_step("1", "Initializing database schema")
    
    try:
        # Import here to avoid issues if run before installation
        sys.path.insert(0, str(Path(__file__).parent))
        from usgs_dashboard.data.database import SchemaManager
        
        schema_mgr = SchemaManager("data/usgs_data.db")
        
        # Check if database exists and has data
        if schema_mgr.db.database_exists():
            info = schema_mgr.get_database_info()
            station_count = info['tables'].get('stations', {}).get('row_count', 0)
            
            if station_count > 0:
                print_success(f"Database already initialized with {station_count} stations")
                return True
        
        # Initialize schema
        success = schema_mgr.initialize_database(force=True)
        if success:
            print_success("Database schema initialized")
            return True
        else:
            print_error("Failed to initialize database schema")
            return False
            
    except Exception as e:
        print_error(f"Error initializing database: {e}")
        return False


def import_stations():
    """Import all station datasets."""
    print_step("2", "Importing station datasets")
    
    try:
        # Check if stations already imported
        from usgs_dashboard.data.database import DatabaseConnection
        db = DatabaseConnection("data/usgs_data.db")
        
        result = db.execute_query("SELECT COUNT(*) as count FROM stations", fetch='one')
        current_count = result[0] if result else 0
        
        if current_count >= 4000:  # Should have ~4,480 total
            print_success(f"Stations already imported ({current_count} in database)")
            return True
        
        # Run import script
        print_info("Importing stations (this may take a minute)...")
        result = subprocess.run(
            [sys.executable, "scripts/data_prep/import_all_stations.py"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print_success("All stations imported successfully")
            return True
        else:
            print_error("Station import failed")
            if result.stderr:
                print(result.stderr)
            return False
            
    except Exception as e:
        print_error(f"Error importing stations: {e}")
        return False


def collect_initial_data():
    """Pre-populate some initial discharge data."""
    print_step("3", "Collecting initial discharge data (optional)")
    
    print_info("This step is optional - data will be fetched on-demand")
    print_info("Pre-populating real-time data for faster initial loads...")
    
    try:
        # Just collect real-time data (fast, ~5-10 minutes)
        result = subprocess.run(
            [sys.executable, "update_realtime_discharge_configurable.py"],
            capture_output=True,
            text=True,
            timeout=900  # 15 minute timeout
        )
        
        if result.returncode == 0:
            print_success("Real-time data collected")
            return True
        else:
            print_warning("Real-time data collection had issues (non-critical)")
            print_info("Data will be fetched on-demand when needed")
            return True  # Non-critical, continue anyway
            
    except subprocess.TimeoutExpired:
        print_warning("Data collection timed out (non-critical)")
        print_info("Data will be fetched on-demand when needed")
        return True
    except Exception as e:
        print_warning(f"Error collecting data: {e} (non-critical)")
        print_info("Data will be fetched on-demand when needed")
        return True


def start_dashboard():
    """Start the dashboard application."""
    print_step("4", "Starting dashboard")
    
    print_success("Starting USGS Streamflow Dashboard...")
    print_info("Dashboard will be available at: http://localhost:8050")
    print_info("Press Ctrl+C to stop\n")
    
    try:
        # Start the dashboard (this will run in foreground)
        subprocess.run([sys.executable, "app.py"])
    except KeyboardInterrupt:
        print("\n")
        print_info("Dashboard stopped")
    except Exception as e:
        print_error(f"Error starting dashboard: {e}")
        return False
    
    return True


def deploy(skip_data=False, setup_only=False, quick=False):
    """Run full deployment process."""
    
    start_time = datetime.now()
    
    print_header("🚀 USGS STREAMFLOW DASHBOARD DEPLOYMENT")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    if quick:
        print_info("Quick mode: Starting dashboard without setup")
        print_info("Assuming database is already initialized\n")
        return start_dashboard()
    
    # Step 0: Check dependencies
    if not check_dependencies():
        print_error("\nDeployment failed: Missing dependencies")
        print_info("Install with: pip install -r requirements.txt")
        return False
    
    # Step 1: Initialize database
    if not initialize_database():
        print_error("\nDeployment failed at database initialization")
        return False
    
    # Step 2: Import stations
    if not import_stations():
        print_error("\nDeployment failed at station import")
        return False
    
    # Step 3: Collect data (optional)
    if not skip_data:
        collect_initial_data()  # Non-critical, continues even if fails
    else:
        print_step("3", "Skipping data pre-population (--skip-data)")
        print_info("Data will be fetched on-demand when needed")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("✅ DEPLOYMENT COMPLETE")
    print(f"Duration: {duration:.1f} seconds\n")
    
    if setup_only:
        print_info("Setup complete. Start dashboard with: python app.py")
        return True
    
    # Step 4: Start dashboard
    return start_dashboard()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="One-command deployment for USGS Streamflow Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py                 # Full deployment + start dashboard
  python deploy.py --skip-data     # Skip data pre-population (faster)
  python deploy.py --setup-only    # Setup database but don't start dashboard
  python deploy.py --quick         # Just start dashboard (skip setup)
  
For fresh deployment, run:
  pip install -r requirements.txt
  python deploy.py

For subsequent starts:
  python deploy.py --quick
        """
    )
    
    parser.add_argument(
        '--skip-data',
        action='store_true',
        help='Skip initial data collection (faster deployment)'
    )
    
    parser.add_argument(
        '--setup-only',
        action='store_true',
        help='Run setup only, do not start dashboard'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick start - skip setup, just start dashboard'
    )
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    success = deploy(
        skip_data=args.skip_data,
        setup_only=args.setup_only,
        quick=args.quick
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
