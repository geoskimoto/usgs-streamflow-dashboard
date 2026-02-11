"""
Tests for water year calculation utilities.

Tests both the functional module (water_year_calculator.py) and
the OOP wrapper (water_year_datetime.py / WaterYearDateTime).
"""

import pytest
from datetime import datetime, date


# ==========================================================================
# water_year_calculator module tests
# ==========================================================================

class TestWaterYearCalculations:
    """Test get_water_year() and related functions."""

    @pytest.fixture(autouse=True)
    def import_module(self):
        from usgs_dashboard.utils.water_year_calculator import (
            get_water_year,
            get_day_of_water_year,
            get_water_year_date_range,
            is_leap_year,
            get_water_year_length,
        )
        self.get_water_year = get_water_year
        self.get_day_of_water_year = get_day_of_water_year
        self.get_water_year_date_range = get_water_year_date_range
        self.is_leap_year = is_leap_year
        self.get_water_year_length = get_water_year_length

    # --- get_water_year ---

    def test_october_is_next_water_year(self):
        """Oct 1 starts a new water year."""
        d = datetime(2025, 10, 1)
        assert self.get_water_year(d) == 2026

    def test_september_is_same_water_year(self):
        """Sep 30 is the end of a water year."""
        d = datetime(2025, 9, 30)
        assert self.get_water_year(d) == 2025

    def test_january_stays_same_water_year(self):
        d = datetime(2026, 1, 15)
        assert self.get_water_year(d) == 2026

    def test_march_stays_same_water_year(self):
        d = datetime(2026, 3, 1)
        assert self.get_water_year(d) == 2026

    def test_december_is_next_water_year(self):
        d = datetime(2025, 12, 25)
        assert self.get_water_year(d) == 2026

    def test_accepts_date_object(self):
        d = date(2026, 2, 15)
        assert self.get_water_year(d) == 2026

    # --- get_day_of_water_year ---

    def test_oct1_is_day_1(self):
        d = datetime(2025, 10, 1)
        assert self.get_day_of_water_year(d) == 1

    def test_oct31_is_day_31(self):
        d = datetime(2025, 10, 31)
        assert self.get_day_of_water_year(d) == 31

    def test_nov1_is_day_32(self):
        d = datetime(2025, 11, 1)
        assert self.get_day_of_water_year(d) == 32

    def test_sep30_is_last_day(self):
        d = datetime(2026, 9, 30)
        wy_len = self.get_water_year_length(2026)
        day = self.get_day_of_water_year(d)
        assert day == wy_len

    def test_jan1_day_number(self):
        d = datetime(2026, 1, 1)
        day = self.get_day_of_water_year(d)
        # Oct (31) + Nov (30) + Dec (31) + Jan 1 = 93
        assert day == 93

    # --- get_water_year_date_range ---

    def test_date_range_wy2026(self):
        start, end = self.get_water_year_date_range(2026)
        assert start.month == 10
        assert start.day == 1
        assert start.year == 2025
        assert end.month == 9
        assert end.day == 30
        assert end.year == 2026

    # --- is_leap_year ---

    def test_2024_is_leap(self):
        assert self.is_leap_year(2024) is True

    def test_2025_is_not_leap(self):
        assert self.is_leap_year(2025) is False

    def test_2000_is_leap(self):
        assert self.is_leap_year(2000) is True

    def test_1900_is_not_leap(self):
        assert self.is_leap_year(1900) is False

    # --- get_water_year_length ---

    def test_non_leap_year_length(self):
        # WY 2026 has Feb 2026 (not a leap year) → 365 days
        assert self.get_water_year_length(2026) == 365

    def test_leap_year_length(self):
        # WY 2024 has Feb 2024 (leap year) → 366 days
        assert self.get_water_year_length(2024) == 366


# ==========================================================================
# WaterYearDateTime class tests
# ==========================================================================

class TestWaterYearDateTime:
    """Test the WaterYearDateTime class."""

    @pytest.fixture
    def handler(self):
        from usgs_dashboard.utils.water_year_datetime import get_water_year_handler
        return get_water_year_handler()

    def test_get_water_year(self, handler):
        d = datetime(2025, 10, 1)
        assert handler.get_water_year(d) == 2026

    def test_get_day_of_water_year(self, handler):
        d = datetime(2025, 10, 1)
        assert handler.get_day_of_water_year(d) == 1

    def test_get_current_water_year_day(self, handler):
        """Should return an integer for today's water year day."""
        day = handler.get_current_water_year_day()
        assert isinstance(day, (int, float))
        assert 1 <= day <= 366

    def test_create_water_year_x_axis(self, handler):
        """Should return tick values and labels for x-axis."""
        result = handler.create_water_year_x_axis()
        assert isinstance(result, (tuple, list, dict))

    def test_get_default_zoom_range(self, handler):
        """Should return a start and end day for default zoom."""
        result = handler.get_default_zoom_range()
        assert result is not None


# ==========================================================================
# Config water year tests
# ==========================================================================

class TestConfigWaterYear:
    """Test water year values in config."""

    def test_current_water_year_is_set(self):
        from usgs_dashboard.utils.config import CURRENT_WATER_YEAR
        assert isinstance(CURRENT_WATER_YEAR, int)
        assert CURRENT_WATER_YEAR >= 2020

    def test_default_start_date_is_valid(self):
        from usgs_dashboard.utils.config import DEFAULT_START_DATE
        assert isinstance(DEFAULT_START_DATE, str)
        # Should be parseable
        parsed = datetime.strptime(DEFAULT_START_DATE, "%Y-%m-%d")
        assert parsed.year >= 1900

    def test_target_states_configured(self):
        from usgs_dashboard.utils.config import TARGET_STATES
        assert isinstance(TARGET_STATES, list)
        assert len(TARGET_STATES) > 0
        assert "OR" in TARGET_STATES
        assert "WA" in TARGET_STATES

    def test_gauge_colors_mapping(self):
        from usgs_dashboard.utils.config import GAUGE_COLORS
        # GAUGE_COLORS maps quality categories, not states
        expected_keys = {"excellent", "good", "fair", "poor", "inactive", "selected"}
        assert expected_keys.issubset(set(GAUGE_COLORS.keys()))
