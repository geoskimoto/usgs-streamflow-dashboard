"""
Database Connection Management

Provides connection pooling and context management for SQLite database access.
"""

import sqlite3
import os
from typing import Optional
from contextlib import contextmanager
from pathlib import Path


class DatabaseConnection:
    """
    Manages database connections with context manager support.
    
    Usage:
        db = DatabaseConnection("data/usgs_data.db")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stations")
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize database connection manager.
        
        Parameters:
        -----------
        db_path : str
            Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
        
    def _ensure_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    @contextmanager
    def get_connection(self, row_factory: bool = False):
        """
        Get a database connection as a context manager.
        
        Parameters:
        -----------
        row_factory : bool
            If True, use Row factory for dictionary-like access
            
        Yields:
        -------
        sqlite3.Connection
            Database connection that will be automatically closed
            
        Example:
        --------
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stations")
        """
        conn = sqlite3.connect(self.db_path)
        
        if row_factory:
            conn.row_factory = sqlite3.Row
        
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = (), 
                     fetch: str = 'all', row_factory: bool = False):
        """
        Execute a query and return results.
        
        Parameters:
        -----------
        query : str
            SQL query to execute
        params : tuple
            Query parameters
        fetch : str
            'all', 'one', or 'none' for fetchall(), fetchone(), or no fetch
        row_factory : bool
            Use Row factory for dictionary-like access
            
        Returns:
        --------
        Query results based on fetch parameter
        """
        with self.get_connection(row_factory=row_factory) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'none':
                return None
            else:
                raise ValueError(f"Invalid fetch parameter: {fetch}")
    
    def execute_many(self, query: str, params_list: list):
        """
        Execute a query multiple times with different parameters.
        
        Parameters:
        -----------
        query : str
            SQL query to execute
        params_list : list
            List of parameter tuples
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Parameters:
        -----------
        table_name : str
            Name of the table to check
            
        Returns:
        --------
        bool
            True if table exists, False otherwise
        """
        query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """
        result = self.execute_query(query, (table_name,), fetch='one')
        return result is not None
    
    def get_table_names(self) -> list:
        """
        Get all table names in the database.
        
        Returns:
        --------
        list
            List of table names
        """
        query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """
        results = self.execute_query(query, fetch='all')
        return [row[0] for row in results]
    
    def get_table_row_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Parameters:
        -----------
        table_name : str
            Name of the table
            
        Returns:
        --------
        int
            Number of rows in the table
        """
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.execute_query(query, fetch='one')
        return result[0] if result else 0
    
    def database_exists(self) -> bool:
        """
        Check if the database file exists.
        
        Returns:
        --------
        bool
            True if database file exists, False otherwise
        """
        return os.path.exists(self.db_path)
    
    def get_database_size(self) -> int:
        """
        Get the size of the database file in bytes.
        
        Returns:
        --------
        int
            Database file size in bytes, or 0 if file doesn't exist
        """
        if self.database_exists():
            return os.path.getsize(self.db_path)
        return 0
    
    def vacuum(self):
        """
        Vacuum the database to reclaim space and optimize performance.
        """
        with self.get_connection() as conn:
            conn.execute("VACUUM")
    
    def reindex(self):
        """
        Rebuild all indexes in the database.
        """
        with self.get_connection() as conn:
            conn.execute("REINDEX")
