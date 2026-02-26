"""
DataOps Adapter Package

Provides unified interface for dashboard to access streamflow data.
Supports REST API mode (with caching) and direct PostgreSQL mode
for same-server deployments.
"""

from .client_adapter import DataOpsAdapter
from .db_adapter import DirectDBAdapter
from .exceptions import AdapterError, APIError, CacheError

__all__ = [
    'DataOpsAdapter',
    'DirectDBAdapter',
    'AdapterError',
    'APIError',
    'CacheError',
]
