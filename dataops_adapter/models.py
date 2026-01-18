"""Data models for adapter layer."""

from typing import Optional
from datetime import datetime


class Station:
    """Station metadata model."""
    
    def __init__(self, **kwargs):
        self.station_number = kwargs.get('station_number')
        self.name = kwargs.get('name')
        self.agency = kwargs.get('agency', 'USGS')
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.state = kwargs.get('state') or kwargs.get('state_code')
        self.huc_code = kwargs.get('huc_code')
        self.is_active = kwargs.get('is_active', True)
        self.basin_name = kwargs.get('basin_name')
        self.last_observation_date = kwargs.get('last_observation_date')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'station_number': self.station_number,
            'name': self.name,
            'agency': self.agency,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'state': self.state,
            'huc_code': self.huc_code,
            'is_active': self.is_active,
            'basin_name': self.basin_name,
            'last_observation_date': self.last_observation_date
        }


class DischargeObservation:
    """Discharge observation model."""
    
    def __init__(self, **kwargs):
        self.station_number = kwargs.get('station_number')
        self.observed_at = kwargs.get('observed_at')
        self.discharge_value = kwargs.get('discharge_value')
        self.unit = kwargs.get('unit', 'cfs')
        self.quality_code = kwargs.get('quality_code', 'A')
        self.data_type = kwargs.get('data_type', 'daily_mean')
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'station_number': self.station_number,
            'observed_at': self.observed_at,
            'discharge_value': self.discharge_value,
            'unit': self.unit,
            'quality_code': self.quality_code,
            'data_type': self.data_type
        }
