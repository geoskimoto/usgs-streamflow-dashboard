"""
Tests for the DataOps API Client (dataops_client/).

Verifies HTTP client behavior, model deserialization, pagination,
error handling, caching, and retry logic — all using mocked responses.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

from dataops_client import DataOpsClient
from dataops_client.models import (
    Station,
    DischargeObservation,
    PullConfiguration,
    PaginatedResponse,
)
from dataops_client.exceptions import (
    DataOpsAPIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    TimeoutError,
    ServerError,
)

from conftest import (
    SAMPLE_STATION_API_RESPONSE,
    SAMPLE_STATION_LIST_RESPONSE,
    SAMPLE_DISCHARGE_RESPONSE,
    SAMPLE_DISCHARGE_OBSERVATION,
    SAMPLE_PAGINATED_DISCHARGE_PAGE1,
    SAMPLE_PAGINATED_DISCHARGE_PAGE2,
    SAMPLE_HEALTH_CHECK,
)


# ==========================================================================
# Model Deserialization Tests
# ==========================================================================

class TestStationModel:
    """Test Station.from_dict() with real API field names."""

    def test_from_dict_basic(self, sample_station_dict):
        station = Station.from_dict(sample_station_dict)
        assert station.station_number == "12108500"
        assert station.name == "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA"
        assert station.agency == "USGS"
        assert station.is_active is True

    def test_from_dict_coordinates(self, sample_station_dict):
        station = Station.from_dict(sample_station_dict)
        assert station.latitude == pytest.approx(47.2916, abs=0.001)
        assert station.longitude == pytest.approx(-122.1192, abs=0.001)

    def test_from_dict_state_mapping(self, sample_station_dict):
        """API uses 'state' but model stores as 'state_code'."""
        station = Station.from_dict(sample_station_dict)
        assert station.state_code == "WA"

    def test_from_dict_basin_mapping(self, sample_station_dict):
        """API uses 'basin' but model stores as 'basin_name'."""
        station = Station.from_dict(sample_station_dict)
        assert station.basin_name == "Puget Sound"

    def test_from_dict_none_coordinates(self):
        data = {
            "station_number": "00000001",
            "name": "Test",
            "agency": "USGS",
            "latitude": None,
            "longitude": None,
        }
        station = Station.from_dict(data)
        assert station.latitude is None
        assert station.longitude is None

    def test_station_name_alias(self, sample_station_dict):
        station = Station.from_dict(sample_station_dict)
        assert station.station_name == station.name

    def test_from_dict_datetime_parsing(self, sample_station_dict):
        station = Station.from_dict(sample_station_dict)
        assert station.created_at is not None
        assert station.updated_at is not None
        assert isinstance(station.created_at, datetime)

    def test_from_dict_missing_optional_fields(self):
        data = {
            "station_number": "00000001",
            "name": "Minimal",
            "agency": "USGS",
        }
        station = Station.from_dict(data)
        assert station.state_code is None
        assert station.huc_code is None
        assert station.basin_name is None
        assert station.is_active is True  # default


class TestDischargeObservationModel:
    """Test DischargeObservation.from_dict() with real API field names."""

    def test_from_dict_basic(self, sample_discharge_observation):
        obs = DischargeObservation.from_dict(sample_discharge_observation)
        assert obs.station_number == "12108500"
        assert obs.discharge_value == pytest.approx(48.8, abs=0.01)
        assert obs.unit == "cfs"
        assert obs.data_type == "daily_mean"
        assert obs.quality_code == "P"

    def test_from_dict_observed_at_parsing(self, sample_discharge_observation):
        obs = DischargeObservation.from_dict(sample_discharge_observation)
        assert isinstance(obs.observed_at, datetime)
        assert obs.observed_at.year == 2026
        assert obs.observed_at.month == 2
        assert obs.observed_at.day == 7

    def test_from_dict_discharge_string_to_float(self):
        """API returns discharge as a decimal string."""
        data = {
            "station_number": "12108500",
            "observed_at": "2026-01-15T00:00:00Z",
            "discharge": "123.4567",
            "unit": "cfs",
            "type": "daily_mean",
        }
        obs = DischargeObservation.from_dict(data)
        assert obs.discharge_value == pytest.approx(123.4567, abs=0.0001)

    def test_from_dict_station_fallback(self):
        """Falls back to 'station' FK when 'station_number' missing."""
        data = {
            "station": 5364,
            "observed_at": "2026-01-01T00:00:00Z",
            "discharge": "10.0",
            "unit": "cfs",
            "type": "daily_mean",
        }
        obs = DischargeObservation.from_dict(data)
        assert obs.station_number == "5364"


class TestPaginatedResponse:
    """Test PaginatedResponse.from_dict() with Station result class."""

    def test_basic_pagination(self, sample_stations_response):
        resp = PaginatedResponse.from_dict(
            sample_stations_response, result_class=Station
        )
        assert resp.count == 2
        assert resp.next is None
        assert resp.previous is None
        assert len(resp.results) == 2
        assert isinstance(resp.results[0], Station)

    def test_pagination_with_next(self):
        data = {
            "count": 100,
            "next": "https://example.com/api/v1/stations/?page=2",
            "previous": None,
            "results": [SAMPLE_STATION_API_RESPONSE],
        }
        resp = PaginatedResponse.from_dict(data, result_class=Station)
        assert resp.count == 100
        assert resp.next is not None
        assert len(resp.results) == 1

    def test_pagination_without_result_class(self, sample_stations_response):
        resp = PaginatedResponse.from_dict(sample_stations_response)
        assert len(resp.results) == 2
        assert isinstance(resp.results[0], dict)


# ==========================================================================
# Client HTTP Tests (mocked)
# ==========================================================================

class TestDataOpsClientInit:
    """Test client initialization."""

    def test_default_base_url(self):
        client = DataOpsClient()
        assert client.base_url == "https://streamflowops.3rdplaces.io"

    def test_custom_base_url(self):
        client = DataOpsClient(base_url="https://custom.example.com/")
        assert client.base_url == "https://custom.example.com"  # trailing slash stripped

    def test_auth_header_set(self):
        client = DataOpsClient(api_token="test-token-123")
        assert "Authorization" in client._session.headers
        assert client._session.headers["Authorization"] == "Bearer test-token-123"

    def test_no_auth_header_without_token(self):
        client = DataOpsClient()
        assert "Authorization" not in client._session.headers

    def test_default_timeout(self):
        client = DataOpsClient()
        assert client.timeout == 60


class TestDataOpsClientRequests:
    """Test API request handling with mocked HTTP responses."""

    def _make_client_with_mock(self):
        """Create a client with a mocked session."""
        client = DataOpsClient(cache_enabled=False)
        client._session = MagicMock()
        return client

    def _mock_response(self, status_code=200, json_data=None, text=""):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or {}
        mock_resp.text = text or json.dumps(json_data or {})
        return mock_resp

    def test_get_stations_success(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            200, SAMPLE_STATION_LIST_RESPONSE
        )

        result = client.get_stations(state="WA", limit=10)
        assert isinstance(result, PaginatedResponse)
        assert len(result.results) == 2
        assert result.results[0].station_number == "12108500"

    def test_get_stations_with_filters(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            200, SAMPLE_STATION_LIST_RESPONSE
        )

        client.get_stations(state="WA", agency="USGS", is_active=True, limit=50)

        call_kwargs = client._session.request.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["state"] == "WA"
        assert params["agency"] == "USGS"
        assert params["is_active"] is True
        assert params["limit"] == 50

    def test_get_single_station(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            200, SAMPLE_STATION_API_RESPONSE
        )

        station = client.get_station("12108500")
        assert isinstance(station, Station)
        assert station.station_number == "12108500"

    def test_get_station_data_basic(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            200, SAMPLE_DISCHARGE_RESPONSE
        )

        result = client.get_station_data(
            "12108500", "2026-01-01", "2026-01-31", data_type="daily_mean"
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert isinstance(result[0], DischargeObservation)
        assert result[0].discharge_value == pytest.approx(55.3)

    def test_get_station_data_auto_pagination(self):
        """Client should follow 'next' URLs to collect all pages."""
        client = self._make_client_with_mock()
        client._session.request.side_effect = [
            self._mock_response(200, SAMPLE_PAGINATED_DISCHARGE_PAGE1),
            self._mock_response(200, SAMPLE_PAGINATED_DISCHARGE_PAGE2),
        ]

        result = client.get_station_data("12108500", "2026-01-01", "2026-01-07")
        assert len(result) == 5  # 3 from page 1 + 2 from page 2

    def test_404_raises_not_found(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            404, text="Not Found"
        )

        with pytest.raises(NotFoundError):
            client.get_station("99999999")

    def test_401_raises_authentication_error(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            401, text="Unauthorized"
        )

        with pytest.raises(AuthenticationError):
            client.get_stations()

    def test_400_raises_validation_error(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            400, text="Invalid parameters"
        )

        with pytest.raises(ValidationError):
            client.get_stations(state="INVALID")

    def test_429_raises_rate_limit(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            429, text="Too many requests"
        )

        with pytest.raises(RateLimitError):
            client.get_stations()

    def test_500_raises_server_error(self):
        client = self._make_client_with_mock()
        client._session.request.return_value = self._mock_response(
            500, text="Internal Server Error"
        )

        with pytest.raises(ServerError):
            client.get_stations()


# ==========================================================================
# Client Caching Tests
# ==========================================================================

class TestClientCaching:
    """Test client-side in-memory cache."""

    def test_cache_hit_returns_cached(self):
        client = DataOpsClient(cache_enabled=True, cache_ttl=300)
        client._session = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_STATION_LIST_RESPONSE
        client._session.request.return_value = mock_resp

        # First call populates cache
        client.get_stations(state="WA")
        # Second call should use cache
        client.get_stations(state="WA")

        # Only one HTTP request should have been made
        assert client._session.request.call_count == 1

    def test_cache_miss_on_different_params(self):
        client = DataOpsClient(cache_enabled=True, cache_ttl=300)
        client._session = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_STATION_LIST_RESPONSE
        client._session.request.return_value = mock_resp

        client.get_stations(state="WA")
        client.get_stations(state="OR")

        assert client._session.request.call_count == 2

    def test_cache_disabled(self):
        client = DataOpsClient(cache_enabled=False)
        client._session = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_STATION_LIST_RESPONSE
        client._session.request.return_value = mock_resp

        client.get_stations(state="WA")
        client.get_stations(state="WA")

        assert client._session.request.call_count == 2

    def test_clear_cache(self):
        client = DataOpsClient(cache_enabled=True)
        client._cache = {"key": ("data", 0)}
        client.clear_cache()
        assert len(client._cache) == 0


# ==========================================================================
# Exception Tests
# ==========================================================================

class TestExceptions:
    """Test custom exception hierarchy."""

    def test_base_error(self):
        err = DataOpsAPIError("test", status_code=400)
        assert str(err) == "test"
        assert err.status_code == 400

    def test_auth_error_is_api_error(self):
        assert issubclass(AuthenticationError, DataOpsAPIError)

    def test_not_found_is_api_error(self):
        assert issubclass(NotFoundError, DataOpsAPIError)

    def test_validation_is_api_error(self):
        assert issubclass(ValidationError, DataOpsAPIError)

    def test_rate_limit_is_api_error(self):
        assert issubclass(RateLimitError, DataOpsAPIError)

    def test_timeout_is_api_error(self):
        assert issubclass(TimeoutError, DataOpsAPIError)

    def test_server_error_is_api_error(self):
        assert issubclass(ServerError, DataOpsAPIError)
