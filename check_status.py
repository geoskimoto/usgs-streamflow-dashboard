#!/usr/bin/env python3
"""
USGS Data System Status Checker

Quick script to check the status of your real-time data system.
"""

import os
import sys
import sqlite3
from datetime import datetime, timezone, timedelta
import subprocess

def check_system_status():
    """Check the overall system status."""
    print("🔍 USGS Real-time Data System Status Check")
    print("=" * 50)
    
    # Check if database exists
    db_path = "data/usgs_cache.db"
    if not os.path.exists(db_path):
        print("❌ Database not found!")
        return
    
    print("✅ Database found")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check real-time data
        cursor.execute('SELECT COUNT(*) FROM realtime_discharge')
        rt_count = cursor.fetchone()[0]
        print(f"📊 Real-time records: {rt_count:,}")
        
        if rt_count > 0:
            cursor.execute('SELECT COUNT(DISTINCT site_no) FROM realtime_discharge')
            rt_sites = cursor.fetchone()[0]
            print(f"📍 Sites with real-time data: {rt_sites}")
            
            cursor.execute('SELECT MIN(datetime_utc), MAX(datetime_utc) FROM realtime_discharge')
            rt_range = cursor.fetchone()
            print(f"📅 Real-time data range: {rt_range[0]} to {rt_range[1]}")
        
        # Check daily data
        cursor.execute('SELECT COUNT(*) FROM streamflow_data')
        daily_count = cursor.fetchone()[0]
        print(f"📊 Daily records: {daily_count:,}")
        
        # Check schedules
        print("\n📅 SCHEDULING STATUS:")
        print("-" * 30)
        cursor.execute('SELECT job_name, enabled, frequency_hours, last_run, next_run FROM update_schedules')
        for job_name, enabled, freq, last_run, next_run in cursor.fetchall():
            status = "🟢 Enabled" if enabled else "🔴 Disabled"
            print(f"{job_name}: {status}")
            print(f"   Frequency: Every {freq} hours")
            print(f"   Last run: {last_run or 'Never'}")
            print(f"   Next run: {next_run or 'Not scheduled'}")
            print()
        
        # Check recent jobs
        print("🔄 RECENT JOB EXECUTIONS:")
        print("-" * 30)
        cursor.execute('''
            SELECT job_name, start_time, end_time, status 
            FROM job_execution_log 
            ORDER BY start_time DESC 
            LIMIT 5
        ''')
        recent_jobs = cursor.fetchall()
        
        if recent_jobs:
            for job_name, start_time, end_time, status in recent_jobs:
                duration = "Running..." if not end_time else "Completed"
                print(f"{job_name}: {start_time} - {status or duration}")
        else:
            print("No job executions recorded")
        
        conn.close()
        
        # Check crontab
        print("\n⏰ CRONTAB STATUS:")
        print("-" * 20)
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                crontab_content = result.stdout
                if 'update_realtime_discharge.py' in crontab_content or 'smart_scheduler.py' in crontab_content:
                    print("✅ Crontab configured")
                    # Show relevant lines
                    for line in crontab_content.split('\n'):
                        if 'update_' in line or 'smart_scheduler' in line:
                            print(f"   {line}")
                else:
                    print("⚠️  No USGS update jobs found in crontab")
            else:
                print("⚠️  No crontab configured")
        except Exception as e:
            print(f"❌ Error checking crontab: {e}")
        
        # Check log files
        print("\n📝 LOG FILES:")
        print("-" * 15)
        log_dir = "logs"
        if os.path.exists(log_dir):
            for log_file in os.listdir(log_dir):
                if log_file.endswith('.log'):
                    log_path = os.path.join(log_dir, log_file)
                    size = os.path.getsize(log_path)
                    mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
                    print(f"📄 {log_file}: {size:,} bytes (modified {mtime})")
        else:
            print("📁 No logs directory found")
        
        print("\n🎯 RECOMMENDATIONS:")
        print("-" * 20)
        
        if rt_count == 0:
            print("❗ No real-time data found. Run: python3 update_realtime_discharge.py")
        
        if not recent_jobs:
            print("❗ No automated jobs executed. Check crontab configuration.")
        
        # Check if data is fresh
        if rt_count > 0:
            cursor = sqlite3.connect(db_path).cursor()
            cursor.execute('SELECT MAX(datetime_utc) FROM realtime_discharge')
            latest_rt = cursor.fetchone()[0]
            if latest_rt:
                latest_dt = datetime.fromisoformat(latest_rt.replace('Z', '+00:00'))
                hours_old = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600
                if hours_old > 4:
                    print(f"⚠️  Real-time data is {hours_old:.1f} hours old. Check if updates are running.")
                else:
                    print(f"✅ Real-time data is fresh ({hours_old:.1f} hours old)")
        
    except Exception as e:
        print(f"❌ Error checking system status: {e}")

if __name__ == "__main__":
    check_system_status()