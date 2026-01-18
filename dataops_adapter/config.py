"""Configuration management for DataOps adapter."""

import os
from typing import Optional
from dotenv import load_dotenv


class AdapterConfig:
    """Configuration for DataOps adapter."""
    
    def __init__(self):
        """Load configuration from environment."""
        load_dotenv()
        
        # API configuration
        self.api_url = os.getenv('DATAOPS_API_URL', 'http://localhost:8000')
        self.api_token = os.getenv('DATAOPS_API_TOKEN')
        self.verify_ssl = os.getenv('DATAOPS_VERIFY_SSL', 'true').lower() == 'true'
        self.timeout = int(os.getenv('DATAOPS_TIMEOUT', '30'))
        
        # Cache configuration
        self.cache_enabled = os.getenv('DATAOPS_CACHE_ENABLED', 'true').lower() == 'true'
        self.cache_ttl = int(os.getenv('DATAOPS_CACHE_TTL', '300'))
        self.cache_db_path = 'data/dataops_cache.db'
        
        # Feature flags
        self.use_dataops_api = os.getenv('USE_DATAOPS_API', 'false').lower() == 'true'
        self.debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    def get_mode(self) -> str:
        """
        Determine adapter mode based on configuration.
        
        Returns:
            'api', 'cache', or 'hybrid'
        """
        if self.use_dataops_api:
            return 'hybrid' if self.cache_enabled else 'api'
        return 'cache'


# Global config instance
config = AdapterConfig()
