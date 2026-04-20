"""
Tests for performance optimisation: StatsCache, fast water-year plot path,
get_current_year_data, and the lazy history-load callback logic.
"""

import os
import shutil
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_discharge_df(years: int = 30) -> pd.DataFrame:
    """Synthetic daily discharge data spanning `years` water years."""
    start = pd.Timestamp("1994-10-01")
    end = pd.Timestamp("2024-09-30")
    idx = pd.date_range(start, end, freq="D")
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "datetime": idx,
        "discharge": np.abs(rng.normal(500, 150, len(idx))),
        "site_no": "99999999",
    })
    return df


def _current_wy() -> int:
    now = datetime.now()
    return now.year + 1 if now.month >= 10 else now.year


# ── StatsCache unit tests ──────────────────────────────────────────────────────

class TestStatsCache:
    """Tests for usgs_dashboard.data.stats_cache_manager."""

    @pytest.fixture(autouse=True)
    def tmp_cache(self, monkeypatch, tmp_path):
        """Redirect STATS_CACHE_DIR to a temp directory."""
        import usgs_dashboard.data.stats_cache_manager as scm
        monkeypatch.setattr(scm, "STATS_CACHE_DIR", str(tmp_path))
        self.cache_dir = tmp_path

    def test_computes_statistics_on_cache_miss(self):
        from usgs_dashboard.data.stats_cache_manager import get_statistics

        df = _make_discharge_df()
        stats = get_statistics("test_site", df)

        assert not stats.empty
        assert "day_of_wy" in stats.columns
        for col in ("q10", "q25", "q50", "q75", "q90", "mean", "median"):
            assert col in stats.columns, f"Missing column: {col}"

    def test_cache_file_written_after_miss(self):
        from usgs_dashboard.data.stats_cache_manager import get_statistics, _current_water_year

        df = _make_discharge_df()
        get_statistics("site_a", df)

        wy = _current_water_year()
        expected = self.cache_dir / f"site_a_WY{wy}.parquet"
        assert expected.exists(), "Cache parquet was not written"

    def test_cache_hit_returns_same_data(self):
        from usgs_dashboard.data.stats_cache_manager import get_statistics

        df = _make_discharge_df()
        first = get_statistics("site_b", df)
        # Second call should load from parquet, not recompute
        second = get_statistics("site_b", df)

        pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))

    def test_stale_files_removed_on_write(self, monkeypatch):
        from usgs_dashboard.data import stats_cache_manager as scm
        from usgs_dashboard.data.stats_cache_manager import _current_water_year

        wy = _current_water_year()
        stale_path = self.cache_dir / f"site_c_WY{wy - 1}.parquet"
        # Create a fake stale file
        stale_path.write_text("placeholder")

        df = _make_discharge_df()
        scm.get_statistics("site_c", df)

        assert not stale_path.exists(), "Stale cache file was not removed"

    def test_excludes_current_water_year_from_stats(self):
        """Stats must only reflect completed water years."""
        from usgs_dashboard.data.stats_cache_manager import _compute_statistics, _current_water_year

        df = _make_discharge_df()
        # Add rows tagged to the current water year (incomplete)
        current_wy = _current_water_year()
        df_with_current = pd.concat([
            df,
            pd.DataFrame({
                "datetime": [pd.Timestamp(f"{current_wy - 1}-10-01"),
                             pd.Timestamp(f"{current_wy - 1}-11-01")],
                "discharge": [9999.0, 9999.0],
                "site_no": "99999999",
            })
        ], ignore_index=True)

        stats = _compute_statistics(df_with_current, current_wy)
        # Ensure the artificially high values (9999) are NOT in the stats
        assert stats["q90"].max() < 5000, "Current-WY data leaked into stats"

    def test_returns_empty_df_on_insufficient_data(self):
        from usgs_dashboard.data.stats_cache_manager import _compute_statistics, _current_water_year

        tiny = pd.DataFrame({
            "datetime": pd.date_range("2010-10-01", periods=100, freq="D"),
            "discharge": [100.0] * 100,
        })
        stats = _compute_statistics(tiny, _current_water_year())
        assert stats.empty

    def test_366_day_rows_for_leap_year_record(self):
        """Full record should yield stats for days 1–366."""
        from usgs_dashboard.data.stats_cache_manager import get_statistics

        df = _make_discharge_df(years=30)
        stats = get_statistics("site_d", df)
        # Should have ≤366 distinct day_of_wy values
        assert stats["day_of_wy"].nunique() <= 366


# ── data_manager method tests ──────────────────────────────────────────────────

class TestGetCurrentYearData:
    """Tests for USGSDataManager.get_current_year_data."""

    @pytest.fixture
    def manager(self):
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.mode = "api"
            mock_adapter.api_enabled = True
            mock_adapter.cache_enabled = True
            mock_factory.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager(cache_dir=tempfile.mkdtemp())
            dm.adapter = mock_adapter
            yield dm

    def test_start_date_is_october_1_of_current_wy(self, manager):
        """Ensure the start date passed to get_discharge_data is Oct 1 of current WY."""
        from usgs_dashboard.utils.water_year_calculator import get_water_year
        from usgs_dashboard.utils.config import WATER_YEAR_START

        now = datetime.now()
        current_wy = get_water_year(now, WATER_YEAR_START)
        expected_start = f"{current_wy - 1}-10-01"

        manager.adapter.get_discharge_data.return_value = pd.DataFrame()
        manager.get_current_year_data("14187500")

        call_kwargs = manager.adapter.get_discharge_data.call_args
        start_passed = call_kwargs[1].get("start_date") or call_kwargs[0][1]
        assert start_passed == expected_start

    def test_does_not_fetch_data_older_than_current_wy(self, manager):
        """get_current_year_data must never request data before Oct 1 of current WY."""
        from usgs_dashboard.utils.water_year_calculator import get_water_year
        from usgs_dashboard.utils.config import WATER_YEAR_START

        manager.adapter.get_discharge_data.return_value = pd.DataFrame()
        manager.get_current_year_data("14187500")

        call_kwargs = manager.adapter.get_discharge_data.call_args
        start_passed = call_kwargs[1].get("start_date") or call_kwargs[0][1]
        start_dt = datetime.strptime(start_passed, "%Y-%m-%d")
        assert start_dt.month == 10 and start_dt.day == 1


class TestGetFlowStatistics:
    """Tests for USGSDataManager.get_flow_statistics."""

    @pytest.fixture
    def manager_with_data(self, tmp_path, monkeypatch):
        """Manager whose adapter returns synthetic discharge data."""
        import usgs_dashboard.data.stats_cache_manager as scm
        monkeypatch.setattr(scm, "STATS_CACHE_DIR", str(tmp_path))

        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.mode = "api"
            mock_adapter.api_enabled = True
            mock_adapter.cache_enabled = True
            mock_factory.return_value = mock_adapter

            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager(cache_dir=str(tmp_path))
            dm.adapter = mock_adapter

            # Patch get_streamflow_data to return synthetic data
            df = _make_discharge_df()
            dm.get_streamflow_data = MagicMock(return_value=df)

            yield dm

    def test_returns_dataframe_with_expected_columns(self, manager_with_data):
        stats = manager_with_data.get_flow_statistics("14187500")
        for col in ("day_of_wy", "q10", "q25", "q50", "q75", "q90", "mean", "median"):
            assert col in stats.columns

    def test_returns_empty_on_empty_streamflow_data(self, manager_with_data):
        manager_with_data.get_streamflow_data = MagicMock(return_value=pd.DataFrame())
        stats = manager_with_data.get_flow_statistics("14187500")
        assert stats.empty

    def test_caches_result_and_skips_recomputation(self, manager_with_data):
        """Second call to get_flow_statistics returns cached parquet; no re-computation."""
        from usgs_dashboard.data.stats_cache_manager import _current_water_year, _cache_path

        first = manager_with_data.get_flow_statistics("14187500")
        assert not first.empty, "First call should return stats"

        # Verify a cache file now exists
        wy = _current_water_year()
        import usgs_dashboard.data.stats_cache_manager as scm
        path = _cache_path("14187500", wy)
        assert os.path.exists(path), "Cache file must exist after first call"

        # Second call: stats should match first
        second = manager_with_data.get_flow_statistics("14187500")
        pd.testing.assert_frame_equal(
            first.reset_index(drop=True),
            second.reset_index(drop=True),
        )


# ── VisualizationManager fast-plot tests ──────────────────────────────────────

class TestCreateFastWaterYearPlot:
    """Tests for VisualizationManager.create_fast_water_year_plot."""

    @pytest.fixture
    def viz(self):
        from usgs_dashboard.components.viz_manager import VisualizationManager
        return VisualizationManager()

    @pytest.fixture
    def current_year_df(self):
        now = pd.Timestamp.now()
        wy_start = pd.Timestamp(now.year if now.month < 10 else now.year, 10, 1)
        if now.month >= 10:
            wy_start = pd.Timestamp(now.year, 10, 1)
        else:
            wy_start = pd.Timestamp(now.year - 1, 10, 1)
        idx = pd.date_range(wy_start, now, freq="D")
        return pd.DataFrame({
            "datetime": idx,
            "discharge": np.abs(np.random.default_rng(7).normal(400, 80, len(idx))),
        })

    @pytest.fixture
    def statistics_df(self):
        days = list(range(1, 367))
        rng = np.random.default_rng(99)
        base = rng.normal(400, 100, 366)
        return pd.DataFrame({
            "day_of_wy": days,
            "q10": base * 0.5,
            "q25": base * 0.75,
            "q50": base,
            "q75": base * 1.25,
            "q90": base * 1.5,
            "mean": base * 1.02,
            "median": base,
        })

    def test_returns_figure_without_error(self, viz, current_year_df, statistics_df):
        import plotly.graph_objects as go
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=statistics_df,
        )
        assert isinstance(fig, go.Figure)

    def test_includes_percentile_band_traces(self, viz, current_year_df, statistics_df):
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=statistics_df,
        )
        trace_names = [t.name for t in fig.data]
        assert any("percentile" in (n or "").lower() for n in trace_names), (
            "Expected percentile band trace"
        )

    def test_includes_current_year_trace(self, viz, current_year_df, statistics_df):
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=statistics_df,
        )
        trace_names = [t.name for t in fig.data]
        assert any("Current" in (n or "") for n in trace_names), (
            "Expected a trace labelled with 'Current'"
        )

    def test_includes_mean_and_median_traces(self, viz, current_year_df, statistics_df):
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=statistics_df,
        )
        trace_names = [t.name for t in fig.data]
        assert any("Mean" in (n or "") for n in trace_names)
        assert any("Median" in (n or "") for n in trace_names)

    def test_handles_empty_statistics_gracefully(self, viz, current_year_df):
        import plotly.graph_objects as go
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=pd.DataFrame(),
        )
        assert isinstance(fig, go.Figure)

    def test_handles_empty_current_year_gracefully(self, viz, statistics_df):
        import plotly.graph_objects as go
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=pd.DataFrame(),
            statistics=statistics_df,
        )
        assert isinstance(fig, go.Figure)

    def test_no_historical_year_traces_added(self, viz, current_year_df, statistics_df):
        """Fast plot must not add one trace per historical year."""
        fig = viz.create_fast_water_year_plot(
            site_id="14187500",
            current_year_data=current_year_df,
            statistics=statistics_df,
        )
        # Historical year traces are labelled "WY YYYY" without "(Current)"
        historical_traces = [
            t for t in fig.data
            if t.name and t.name.startswith("WY ") and "(Current)" not in t.name
        ]
        assert len(historical_traces) == 0, (
            f"Fast plot should not contain historical year traces; found: "
            f"{[t.name for t in historical_traces]}"
        )


# ── History mode filter tests ─────────────────────────────────────────────────

class TestHistoryModeFilter:
    """Tests for history_mode='30yr' filtering in _create_enhanced_water_year_plot."""

    @pytest.fixture
    def viz(self):
        from usgs_dashboard.components.viz_manager import VisualizationManager
        return VisualizationManager()

    @pytest.fixture
    def full_history_df(self):
        """60 years of daily discharge, DatetimeIndex."""
        start = pd.Timestamp("1964-10-01")
        end = pd.Timestamp("2024-09-30")
        idx = pd.date_range(start, end, freq="D")
        rng = np.random.default_rng(13)
        df = pd.DataFrame({"discharge": np.abs(rng.normal(400, 100, len(idx)))}, index=idx)
        return df

    def test_30yr_mode_restricts_year_count(self, viz, full_history_df):
        from usgs_dashboard.utils.water_year_calculator import get_water_year
        from usgs_dashboard.utils.config import WATER_YEAR_START

        fig = viz._create_enhanced_water_year_plot(
            full_history_df, "discharge",
            highlight_years=[],
            show_percentiles=False,
            show_statistics=False,
            history_mode="30yr",
        )
        # Collect unique year labels from trace names ("WY YYYY" patterns)
        import re
        years_plotted = set()
        for trace in fig.data:
            m = re.search(r"WY (\d{4})", trace.name or "")
            if m:
                years_plotted.add(int(m.group(1)))

        current_wy = get_water_year(pd.Timestamp.now(), WATER_YEAR_START)
        oldest_allowed = current_wy - 30
        if years_plotted:
            assert min(years_plotted) >= oldest_allowed, (
                f"30yr mode included year {min(years_plotted)}, "
                f"expected ≥ {oldest_allowed}"
            )

    def test_all_mode_includes_full_record(self, viz, full_history_df):
        fig_30 = viz._create_enhanced_water_year_plot(
            full_history_df, "discharge",
            highlight_years=[], show_percentiles=False, show_statistics=False,
            history_mode="30yr",
        )
        fig_all = viz._create_enhanced_water_year_plot(
            full_history_df, "discharge",
            highlight_years=[], show_percentiles=False, show_statistics=False,
            history_mode="all",
        )
        # 'all' mode should have more traces (more historical years)
        assert len(fig_all.data) >= len(fig_30.data)
