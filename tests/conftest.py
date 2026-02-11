"""
Shared test fixtures for the USGS Streamflow Dashboard test suite.

Provides mock API responses, sample data, and configured test clients.
"""

import os
import sys
import json
import pytest
import tempfile
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Sample API response data
# ---------------------------------------------------------------------------

SAMPLE_STATION_API_RESPONSE = {
    "station_number": "12108500",
    "name": "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA",
    "agency": "USGS",
    "latitude": 47.2916,
    "longitude": -122.1192,
    "state": "WA",
    "huc_code": "17110013",
    "basin": "Puget Sound",
    "is_active": True,
    "last_observation_date": None,
    "created_at": "2025-01-01T00:00:00Z",
    "last_updated": "2026-02-01T00:00:00Z",
}

SAMPLE_STATION_LIST_RESPONSE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "station_number": "12108500",
            "name": "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA",
            "agency": "USGS",
            "latitude": 47.2916,
            "longitude": -122.1192,
            "state": "WA",
            "huc_code": None,
            "basin": None,
            "is_active": True,
        },
        {
            "station_number": "12113150",
            "name": "GREEN RIVER NEAR AUBURN, WA",
            "agency": "USGS",
            "latitude": 47.3052,
            "longitude": -122.2118,
            "state": "WA",
            "huc_code": None,
            "basin": None,
            "is_active": True,
        },
    ],
}

SAMPLE_DISCHARGE_OBSERVATION = {
    "id": 2706009,
    "station": 5364,
    "station_number": "12108500",
    "observed_at": "2026-02-07T00:00:00Z",
    "discharge": "48.8000",
    "unit": "cfs",
    "type": "daily_mean",
    "quality_code": "P",
}

SAMPLE_DISCHARGE_RESPONSE = {
    "count": 3,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": 1,
            "station": 5364,
            "station_number": "12108500",
            "observed_at": "2026-01-01T00:00:00Z",
            "discharge": "55.3000",
            "unit": "cfs",
            "type": "daily_mean",
            "quality_code": "P",
        },
        {
            "id": 2,
            "station": 5364,
            "station_number": "12108500",
            "observed_at": "2026-01-02T00:00:00Z",
            "discharge": "62.1000",
            "unit": "cfs",
            "type": "daily_mean",
            "quality_code": "P",
        },
        {
            "id": 3,
            "station": 5364,
            "station_number": "12108500",
            "observed_at": "2026-01-03T00:00:00Z",
            "discharge": "47.5000",
            "unit": "cfs",
            "type": "daily_mean",
            "quality_code": "A",
        },
    ],
}

SAMPLE_PAGINATED_DISCHARGE_PAGE1 = {
    "count": 5,
    "next": "https://streamflowops.3rdplaces.io/api/v1/observations/discharge/?limit=3&page=2&station_number=12108500",
    "previous": None,
    "results": SAMPLE_DISCHARGE_RESPONSE["results"],
}

SAMPLE_PAGINATED_DISCHARGE_PAGE2 = {
    "count": 5,
    "next": None,
    "previous": "https://streamflowops.3rdplaces.io/api/v1/observations/discharge/?limit=3&page=1&station_number=12108500",
    "results": [
        {
            "id": 4,
            "station": 5364,
            "station_number": "12108500",
            "observed_at": "2026-01-04T00:00:00Z",
            "discharge": "51.0000",
            "unit": "cfs",
            "type": "daily_mean",
            "quality_code": "A",
        },
        {
            "id": 5,
            "station": 5364,
            "station_number": "12108500",
            "observed_at": "2026-01-05T00:00:00Z",
            "discharge": "44.2000",
            "unit": "cfs",
            "type": "daily_mean",
            "quality_code": "A",
        },
    ],
}

SAMPLE_HEALTH_CHECK = {
    "status": "healthy",
    "database": "connected",
    "version": "1.0.0",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_station_dict():
    """Return a single station dict as from the API."""
    return SAMPLE_STATION_API_RESPONSE.copy()


@pytest.fixture
def sample_stations_response():
    """Return a paginated stations list response."""
    return json.loads(json.dumps(SAMPLE_STATION_LIST_RESPONSE))


@pytest.fixture
def sample_discharge_response():
    """Return a paginated discharge observations response."""
    return json.loads(json.dumps(SAMPLE_DISCHARGE_RESPONSE))


@pytest.fixture
def sample_discharge_observation():
    """Return a single discharge observation dict."""
    return SAMPLE_DISCHARGE_OBSERVATION.copy()


@pytest.fixture
def sample_stations_df():
    """Return a DataFrame mimicking adapter station output."""
    return pd.DataFrame([
        {
            "station_number": "12108500",
            "name": "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA",
            "agency": "USGS",
            "latitude": 47.2916,
            "longitude": -122.1192,
            "state": "WA",
            "huc_code": None,
            "is_active": True,
            "basin_name": None,
        },
        {
            "station_number": "12113150",
            "name": "GREEN RIVER NEAR AUBURN, WA",
            "agency": "USGS",
            "latitude": 47.3052,
            "longitude": -122.2118,
            "state": "WA",
            "huc_code": None,
            "is_active": True,
            "basin_name": None,
        },
        {
            "station_number": "10366000",
            "name": "TWENTYMILE CREEK NEAR ADEL,OREG.",
            "agency": "USGS",
            "latitude": 42.0721,
            "longitude": -119.9627,
            "state": "OR",
            "huc_code": None,
            "is_active": True,
            "basin_name": None,
        },
    ])


@pytest.fixture
def sample_discharge_df():
    """Return a DataFrame mimicking adapter discharge output."""
    return pd.DataFrame([
        {
            "date": pd.Timestamp("2026-01-01", tz="UTC"),
            "station_number": "12108500",
            "discharge": 55.3,
            "unit": "cfs",
            "quality": "P",
        },
        {
            "date": pd.Timestamp("2026-01-02", tz="UTC"),
            "station_number": "12108500",
            "discharge": 62.1,
            "unit": "cfs",
            "quality": "P",
        },
        {
            "date": pd.Timestamp("2026-01-03", tz="UTC"),
            "station_number": "12108500",
            "discharge": 47.5,
            "unit": "cfs",
            "quality": "A",
        },
    ])


@pytest.fixture
def temp_cache_db(tmp_path):
    """Provide a temporary SQLite cache database path."""
    return str(tmp_path / "test_cache.db")


@pytest.fixture
def mock_api_session():
    """Provide a mocked requests.Session for API client tests."""
    with patch("dataops_client.client.requests.Session") as MockSession:
        session_instance = MagicMock()
        MockSession.return_value = session_instance
        yield session_instance


@pytest.fixture
def env_dataops_enabled(monkeypatch):
    """Set environment variables for DataOps API enabled mode."""
    monkeypatch.setenv("USE_DATAOPS_API", "true")
    monkeypatch.setenv("DATAOPS_API_URL", "https://streamflowops.3rdplaces.io")
    monkeypatch.setenv("DATAOPS_API_TOKEN", "")
    monkeypatch.setenv("DATAOPS_CACHE_ENABLED", "false")
    monkeypatch.setenv("DATAOPS_TIMEOUT", "30")


@pytest.fixture
def env_cache_only(monkeypatch):
    """Set environment variables for cache-only mode."""
    monkeypatch.setenv("USE_DATAOPS_API", "false")
    monkeypatch.setenv("DATAOPS_CACHE_ENABLED", "true")
    monkeypatch.setenv("DATAOPS_CACHE_TTL", "300")


@pytest.fixture
def env_hybrid(monkeypatch):
    """Set environment variables for hybrid mode."""
    monkeypatch.setenv("USE_DATAOPS_API", "true")
    monkeypatch.setenv("DATAOPS_API_URL", "https://streamflowops.3rdplaces.io")
    monkeypatch.setenv("DATAOPS_CACHE_ENABLED", "true")
    monkeypatch.setenv("DATAOPS_CACHE_TTL", "300")
    monkeypatch.setenv("DATAOPS_TIMEOUT", "30")
