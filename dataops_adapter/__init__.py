"""
DataOps Adapter Package

Provides unified interface for dashboard to access streamflow data
from DataOps API with local caching and fallback capabilities.
"""

from .client_adapter import DataOpsAdapter
from .exceptions import AdapterError, APIError, CacheError

__all__ = ['DataOpsAdapter', 'AdapterError', 'APIError', 'CacheError']
