#!/usr/bin/env python3
"""
Smart Scheduler for USGS Data Updates

This script checks the database schedule configuration and runs jobs
only when they're due. Use this with a frequent cron job (every 15 minutes)
for more flexible, database-driven scheduling.

Usage in crontab:
*/15 * * * * cd /path/to/project && python3 smart_scheduler.py
"""

import os
import sys
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler()
    ]
)

class SmartScheduler:
    """Database-driven job scheduler for USGS data updates."""
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        self.db_path = db_path
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        
    def check_and_run_jobs(self):
        """Check database for due jobs and execute them."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all enabled jobs
            cursor.execute('''
                SELECT job_name, frequency_hours, last_run, next_run, retention_days
                FROM schedules 
                WHERE enabled = 1
            ''')
            
            jobs = cursor.fetchall()
            current_time = datetime.now(timezone.utc)
            
            for job_name, frequency_hours, last_run, next_run, retention_days in jobs:
                # Parse next_run time
                if next_run:
                    try:
                        next_run_dt = datetime.fromisoformat(next_run.replace('Z', '+00:00'))
                        if next_run_dt.tzinfo is None:
                            next_run_dt = next_run_dt.replace(tzinfo=timezone.utc)
                    except:
                        next_run_dt = None
                else:
                    next_run_dt = None
                
                # Determine if job should run
                should_run = False
                if next_run_dt is None:  # First run
                    should_run = True
                elif current_time >= next_run_dt:  # Scheduled time reached
                    should_run = True
                
                if should_run:
                    self._execute_job(job_name, frequency_hours, retention_days)
                    
            conn.close()
            
        except Exception as e:
            logging.error(f"Error in scheduler: {e}")
    
    def _execute_job(self, job_name: str, frequency_hours: int, retention_days: int):
        """Execute a specific job."""
        try:
            # Determine script to run (using configurable versions)
            if job_name == 'realtime_update':
                script = 'update_realtime_discharge_configurable.py'
            elif job_name == 'daily_update':
                script = 'update_daily_discharge_configurable.py'
            else:
                logging.warning(f"Unknown job: {job_name}")
                return
            
            logging.info(f"Starting job: {job_name}")
            
            # Log job start
            self._log_job_start(job_name)
            
            # Execute script
            cmd = [sys.executable, script]
            if retention_days and job_name == 'realtime_update':
                cmd.extend(['--retention-days', str(retention_days)])
            
            result = subprocess.run(
                cmd, 
                cwd=self.project_root,
                capture_output=True, 
                text=True, 
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logging.info(f"Job {job_name} completed successfully")
                self._log_job_completion(job_name, 'SUCCESS', result.stdout)
                self._update_next_run(job_name, frequency_hours)
            else:
                logging.error(f"Job {job_name} failed: {result.stderr}")
                self._log_job_completion(job_name, 'FAILED', result.stderr)
                
        except subprocess.TimeoutExpired:
            logging.error(f"Job {job_name} timed out")
            self._log_job_completion(job_name, 'TIMEOUT', 'Job exceeded 1 hour timeout')
        except Exception as e:
            logging.error(f"Error executing {job_name}: {e}")
            self._log_job_completion(job_name, 'ERROR', str(e))
    
    def _log_job_start(self, job_name: str):
        """Log job start in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_time = datetime.now(timezone.utc).isoformat()
            cursor.execute('''
                INSERT INTO job_execution_log (job_name, start_time) 
                VALUES (?, ?)
            ''', (job_name, start_time))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error logging job start: {e}")
    
    def _log_job_completion(self, job_name: str, status: str, output: str):
        """Log job completion in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            end_time = datetime.now(timezone.utc).isoformat()
            cursor.execute('''
                UPDATE job_execution_log 
                SET end_time = ?, status = ?, output = ?
                WHERE job_name = ? AND end_time IS NULL
                ORDER BY start_time DESC
                LIMIT 1
            ''', (end_time, status, output, job_name))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error logging job completion: {e}")
    
    def _update_next_run(self, job_name: str, frequency_hours: int):
        """Update next run time in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            next_run = now + timedelta(hours=frequency_hours)
            
            cursor.execute('''
                UPDATE schedules 
                SET last_run = ?, next_run = ?, modified_at = ?
                WHERE job_name = ?
            ''', (now.isoformat(), next_run.isoformat(), now.isoformat(), job_name))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Next run for {job_name}: {next_run}")
            
        except Exception as e:
            logging.error(f"Error updating next run time: {e}")

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    scheduler = SmartScheduler()
    scheduler.check_and_run_jobs()