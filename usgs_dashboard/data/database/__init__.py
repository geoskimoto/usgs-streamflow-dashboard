"""
Database Layer for USGS Streamflow Dashboard

This module provides a clean separation of database operations following the Repository pattern.
All database access should go through these repository classes rather than direct SQL queries.

Architecture:
- connection.py: Database connection management
- schema_manager.py: Schema creation and migrations
- station_repository.py: Station metadata operations
- streamflow_repository.py: Daily streamflow data operations
- realtime_repository.py: Realtime discharge data operations
- config_repository.py: Configuration and schedule management
"""

from .connection import DatabaseConnection
from .schema_manager import SchemaManager
from .station_repository import StationRepository
from .streamflow_repository import StreamflowRepository
from .realtime_repository import RealtimeRepository
from .config_repository import ConfigRepository

__all__ = [
    'DatabaseConnection',
    'SchemaManager',
    'StationRepository',
    'StreamflowRepository',
    'RealtimeRepository',
    'ConfigRepository',
]
