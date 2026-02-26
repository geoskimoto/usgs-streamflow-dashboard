"""
DataOps Adapter Package

Provides unified interface for dashboard to access streamflow data.
Supports REST API mode (with caching) and direct PostgreSQL mode
for same-server deployments.

Adapter selection is controlled by the USE_DATAOPS_API environment variable:
  USE_DATAOPS_API=true  (default) — DataOpsAdapter via REST API (Render, remote)
  USE_DATAOPS_API=false           — DirectDBAdapter via PostgreSQL (same-server)
"""

import os

from .client_adapter import DataOpsAdapter
from .db_adapter import DirectDBAdapter
from .exceptions import AdapterError, APIError, CacheError


def get_adapter():
    """
    Return the appropriate data adapter based on the USE_DATAOPS_API env var.

    USE_DATAOPS_API=true  (default) → DataOpsAdapter (REST API)
    USE_DATAOPS_API=false           → DirectDBAdapter (direct PostgreSQL)
    """
    use_api = os.getenv('USE_DATAOPS_API', 'true').lower() == 'true'
    if use_api:
        return DataOpsAdapter()
    return DirectDBAdapter()


__all__ = [
    'DataOpsAdapter',
    'DirectDBAdapter',
    'get_adapter',
    'AdapterError',
    'APIError',
    'CacheError',
]
