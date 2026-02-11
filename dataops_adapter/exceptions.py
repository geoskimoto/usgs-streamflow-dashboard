"""Custom exceptions for DataOps adapter."""


class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class APIError(AdapterError):
    """Exception raised when API communication fails."""
    pass


class CacheError(AdapterError):
    """Exception raised when cache operations fail."""
    pass


class ConfigurationError(AdapterError):
    """Exception raised for configuration issues."""
    pass
