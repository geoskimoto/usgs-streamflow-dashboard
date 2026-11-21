"""Water-year volume (docs/superpowers/plans/2026-11-20-water-year-volume-plot.md, R1-R12, R20, R24, R25).

Written BEFORE the implementation exists; every test is expected to fail until
usgs_dashboard/utils/water_year_volume.py and data_manager.get_water_year_volume land.

ASSUMED INTERFACES (the plan leaves these open; the implementer must match or
tell the test author to change the test, never the reverse):

  usgs_dashboard.utils.water_year_volume
    WYV_MAX_MISSING_FRAC == 0.05, WYV_MIN_YEARS == 10   (also in utils/config.py)
    cfs_days_to_kaf(x)           -> x * 86400/43560 / 1000   (scalar/array/Series)
    daily_volume(df)             -> DataFrame, same rows as df, with column
                                    'daily_cfs_days' (df has 'datetime', 'discharge'
                                    and optional 'unit' in {cfs, cms}; NaN stays NaN)
    water_year_volume_table(df)  -> (table, summary)
        table:   columns water_year, day_of_wy, daily_cfs_days, cum_cfs_days;
                 one row per ELAPSED day of each water year (Oct 1 .. last day of
                 that year, or .. last observed date for the final year). A day
                 with no observation has daily_cfs_days NaN (or 0) and cum
                 carried forward flat.
        summary: DataFrame with water_year (column or index), elapsed_days,
                 observed_days, missing_days.
    cumulative_bands(table, current_wy, summary=None, site_id=None) -> dict with
        'bands' (DataFrame: day_of_wy, q10, q25, q50, q75, q90, median; cfs-days;
                 numpy default linear percentile across years) or None,
        'has_bands' (bool), 'n_years' (int qualifying historical years),
        'excluded_years' (list of water years dropped for gaps).

  USGSDataManager.get_water_year_volume(site_id) -> dict with
        'status' in {'ok','empty','error'}, 'site_id', 'current_wy', 'table',
        'summary', 'bands' (the cumulative_bands dict), 'daily_bands'
        (DataFrame day_of_wy, q10..q90, mean, median in cfs-days),
        'current_missing_days' (int). Never raises.
"""
import logging
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

CFS_DAY_TO_KAF = 86400.0 / 43560.0 / 1000.0   # 0.001983471...
CFS_PER_CMS = 35.3146667
SEEDS = list(range(20))


def _wyv():
    from usgs_dashboard.utils import water_year_volume
    return water_year_volume


def _frame(wys, flow=lambda wy, i: 100.0, current=None, drop=(), unit=None):
    """Daily frame for complete water years `wys`; `current`=(wy, n_days) adds a partial year.
    `drop` is a set of Timestamps removed (gaps)."""
    parts = []
    for wy in wys:
        idx = pd.date_range(f"{wy - 1}-10-01", f"{wy}-09-30", freq="D")
        parts.append(pd.DataFrame({"datetime": idx,
                                   "discharge": [flow(wy, i) for i in range(len(idx))]}))
    if current:
        wy, n = current
        idx = pd.date_range(f"{wy - 1}-10-01", periods=n, freq="D")
        parts.append(pd.DataFrame({"datetime": idx,
                                   "discharge": [flow(wy, i) for i in range(n)]}))
    df = pd.concat(parts, ignore_index=True)
    if len(drop):
        df = df[~df["datetime"].isin(set(pd.to_datetime(list(drop))))].reset_index(drop=True)
    df["site_no"] = "SITE"
    if unit:
        df["unit"] = unit
    return df


def _summ(summary, wy):
    s = summary if "water_year" in summary.columns else summary.reset_index()
    return s[s["water_year"] == wy].iloc[0]


def _year(table, wy):
    return table[table["water_year"] == wy].sort_values("day_of_wy")


# ------------------------------------------------------------------ constants

def test_thresholds_have_approved_defaults():
    m = _wyv()
    assert m.WYV_MAX_MISSING_FRAC == 0.05
    assert m.WYV_MIN_YEARS == 10


def test_thresholds_reachable_from_config():
    from usgs_dashboard.utils import config
    assert config.WYV_MAX_MISSING_FRAC == 0.05
    assert config.WYV_MIN_YEARS == 10


# ------------------------------------------------------------------ R1

def test_r1_one_cfs_day_is_86400_over_43560_acre_feet():
    assert _wyv().cfs_days_to_kaf(1000.0) == pytest.approx(86400 / 43560, rel=1e-9)
    assert _wyv().cfs_days_to_kaf(1.0) == pytest.approx(1.983471 / 1000, rel=1e-6)


def test_r1_kaf_zero_and_vectorised():
    f = _wyv().cfs_days_to_kaf
    assert f(0.0) == 0.0
    out = f(np.array([0.0, 10.0, 20.0]))
    np.testing.assert_allclose(out, np.array([0, 10, 20]) * CFS_DAY_TO_KAF)


@pytest.mark.parametrize("seed", SEEDS)
def test_r1_property_kaf_is_linear_scale_of_cfs_days(seed):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 1e6, 50)
    np.testing.assert_allclose(_wyv().cfs_days_to_kaf(x), x * CFS_DAY_TO_KAF, rtol=1e-9)


# ------------------------------------------------------------------ R2

def test_r2_daily_mean_cfs_equals_cfs_days_of_that_day():
    df = _frame([2020], flow=lambda wy, i: 10.0 + i)
    out = _wyv().daily_volume(df)
    np.testing.assert_allclose(out["daily_cfs_days"].to_numpy(), df["discharge"].to_numpy())


def test_r2_nan_discharge_stays_nan_not_zero_filled():
    df = _frame([2020])
    df.loc[5, "discharge"] = np.nan
    out = _wyv().daily_volume(df)
    assert np.isnan(out["daily_cfs_days"].iloc[5])


# ------------------------------------------------------------------ R3

def test_r3_cms_is_converted_to_cfs_before_volume():
    df = _frame([2020], flow=lambda wy, i: 10.0, unit="cms")
    out = _wyv().daily_volume(df)
    np.testing.assert_allclose(out["daily_cfs_days"].to_numpy(), 10.0 * CFS_PER_CMS, rtol=1e-6)


def test_r3_cms_native_and_cfs_equivalent_give_identical_volumes():
    cms = _frame([2018, 2019], flow=lambda wy, i: 3.0 + (i % 7), unit="cms")
    cfs = cms.copy()
    cfs["discharge"] = cfs["discharge"] * CFS_PER_CMS
    cfs["unit"] = "cfs"
    t1, _ = _wyv().water_year_volume_table(cms)
    t2, _ = _wyv().water_year_volume_table(cfs)
    np.testing.assert_allclose(t1["cum_cfs_days"].to_numpy(), t2["cum_cfs_days"].to_numpy(), rtol=1e-6)


def test_r3_missing_unit_column_means_cfs():
    df = _frame([2020], flow=lambda wy, i: 5.0)
    out = _wyv().daily_volume(df)
    np.testing.assert_allclose(out["daily_cfs_days"].to_numpy(), 5.0)


@pytest.mark.parametrize("seed", SEEDS)
def test_r3_property_cms_equals_cfs_equivalent(seed):
    rng = np.random.default_rng(seed)
    cms = _frame([2015], flow=lambda wy, i: float(rng.uniform(0.1, 500)), unit="cms")
    cfs = cms.assign(discharge=cms["discharge"] * CFS_PER_CMS, unit="cfs")
    a = _wyv().daily_volume(cms)["daily_cfs_days"].to_numpy()
    b = _wyv().daily_volume(cfs)["daily_cfs_days"].to_numpy()
    np.testing.assert_allclose(a, b, rtol=1e-6)


# ------------------------------------------------------------------ R5 / R7

def test_r5_table_has_required_columns():
    table, summary = _wyv().water_year_volume_table(_frame([2020]))
    assert {"water_year", "day_of_wy", "daily_cfs_days", "cum_cfs_days"} <= set(table.columns)
    assert {"elapsed_days", "observed_days", "missing_days"} <= set(
        summary.columns.union(summary.index.names))


def test_r5_day_of_wy_matches_water_year_calculator():
    from usgs_dashboard.utils.water_year_calculator import get_day_of_water_year, get_water_year
    df = _frame([2019, 2020])
    table, _ = _wyv().water_year_volume_table(df)
    # table has one row per day; align on order within each year
    for wy in (2019, 2020):
        t = _year(table, wy)
        dates = pd.date_range(f"{wy - 1}-10-01", f"{wy}-09-30")
        assert list(t["day_of_wy"]) == [get_day_of_water_year(d) for d in dates]
        assert all(get_water_year(d) == wy for d in dates)


def test_r5_cumulative_is_running_sum_from_oct1():
    table, _ = _wyv().water_year_volume_table(_frame([2021], flow=lambda wy, i: 1.0 + i))
    t = _year(table, 2021)
    np.testing.assert_allclose(t["cum_cfs_days"].to_numpy(),
                               np.cumsum(t["daily_cfs_days"].fillna(0).to_numpy()))
    assert t["cum_cfs_days"].iloc[0] == pytest.approx(1.0)


def test_r7_sep30_belongs_to_ending_water_year_and_oct1_to_next():
    # contiguous Sep 28 -> Oct 3, flows 1..6
    idx = pd.date_range("2023-09-28", "2023-10-03")
    df = pd.DataFrame({"datetime": idx, "discharge": [1., 2, 3, 4, 5, 6], "site_no": "S"})
    table, _ = _wyv().water_year_volume_table(df)
    assert set(table["water_year"]) == {2023, 2024}
    y23, y24 = _year(table, 2023), _year(table, 2024)
    # Sep 30 2023 is the last day of WY2023 (non-leap year => day 365)
    assert y23["day_of_wy"].iloc[-1] == 365
    assert y23["daily_cfs_days"].iloc[-1] == pytest.approx(3.0)
    # Oct 1 2023 starts WY2024 at day 1 with its own cumulative restart
    assert y24["day_of_wy"].iloc[0] == 1
    assert y24["cum_cfs_days"].iloc[0] == pytest.approx(4.0)
    assert y24["cum_cfs_days"].iloc[-1] == pytest.approx(4.0 + 5.0 + 6.0)


def test_r7_leap_water_year_has_366_days_and_day_366_is_sep30():
    table, summary = _wyv().water_year_volume_table(_frame([2024, 2025]))
    y24, y25 = _year(table, 2024), _year(table, 2025)
    assert len(y24) == 366 and y24["day_of_wy"].iloc[-1] == 366
    assert len(y25) == 365 and y25["day_of_wy"].iloc[-1] == 365
    assert _summ(summary, 2024)["missing_days"] == 0
    assert _summ(summary, 2024)["elapsed_days"] == 366


def test_r7_leap_year_total_volume_counts_feb29():
    table, _ = _wyv().water_year_volume_table(_frame([2024], flow=lambda wy, i: 2.0))
    assert _year(table, 2024)["cum_cfs_days"].iloc[-1] == pytest.approx(2.0 * 366)


# ------------------------------------------------------------------ R6 / R9 gaps

@pytest.mark.parametrize("seed", SEEDS)
def test_r6_property_cumulative_monotone_and_ends_at_sum_of_daily(seed):
    rng = np.random.default_rng(seed)
    wys = [2011, 2012, 2013]
    df = _frame(wys, flow=lambda wy, i: float(rng.uniform(0, 1000)))
    drop = rng.choice(df["datetime"].to_numpy(), size=int(rng.integers(0, 40)), replace=False)
    df = df[~df["datetime"].isin(drop)].reset_index(drop=True)
    table, _ = _wyv().water_year_volume_table(df)
    for wy in wys:
        t = _year(table, wy)
        cum = t["cum_cfs_days"].to_numpy()
        assert np.all(np.diff(cum) >= -1e-9)
        assert cum[-1] == pytest.approx(t["daily_cfs_days"].fillna(0).sum(), rel=1e-9)
        # and equals the raw input sum for that year
        raw = df[(df["datetime"] >= f"{wy - 1}-10-01") & (df["datetime"] <= f"{wy}-09-30")]
        assert cum[-1] == pytest.approx(raw["discharge"].sum(), rel=1e-9)


def test_r6_zero_flow_is_observed_not_missing():
    df = _frame([2020], flow=lambda wy, i: 0.0)
    table, summary = _wyv().water_year_volume_table(df)
    assert _summ(summary, 2020)["missing_days"] == 0
    assert _year(table, 2020)["cum_cfs_days"].iloc[-1] == 0.0


def test_r9_missing_day_contributes_no_volume_and_is_not_interpolated():
    gap = pd.Timestamp("2020-01-15")
    df = _frame([2020], flow=lambda wy, i: 10.0, drop=[gap])
    table, summary = _wyv().water_year_volume_table(df)
    t = _year(table, 2020)
    assert _summ(summary, 2020)["missing_days"] == 1
    assert t["cum_cfs_days"].iloc[-1] == pytest.approx(10.0 * (len(t) - 1))   # lower bound
    d = (gap - pd.Timestamp("2019-10-01")).days + 1
    row = t[t["day_of_wy"] == d].iloc[0]
    assert (np.isnan(row["daily_cfs_days"]) or row["daily_cfs_days"] == 0.0)
    prev = t[t["day_of_wy"] == d - 1].iloc[0]
    assert row["cum_cfs_days"] == pytest.approx(prev["cum_cfs_days"])  # flat across gap


def test_r9_nan_discharge_counts_as_missing_day():
    df = _frame([2020])
    df.loc[3, "discharge"] = np.nan
    _, summary = _wyv().water_year_volume_table(df)
    assert _summ(summary, 2020)["missing_days"] == 1
    assert _summ(summary, 2020)["observed_days"] == 365   # WY2020 is leap (366) minus 1


@pytest.mark.parametrize("seed", SEEDS)
def test_r9_property_gaps_never_create_volume(seed):
    rng = np.random.default_rng(seed)
    full = _frame([2014], flow=lambda wy, i: float(rng.uniform(1, 100)))
    drop = rng.choice(full["datetime"].to_numpy(), size=int(rng.integers(1, 60)), replace=False)
    gapped = full[~full["datetime"].isin(drop)].reset_index(drop=True)
    t_full, _ = _wyv().water_year_volume_table(full)
    t_gap, s_gap = _wyv().water_year_volume_table(gapped)
    assert _year(t_gap, 2014)["cum_cfs_days"].iloc[-1] <= _year(t_full, 2014)["cum_cfs_days"].iloc[-1]
    assert _summ(s_gap, 2014)["missing_days"] == len(drop)
    # pointwise: gapped cumulative never exceeds the complete cumulative
    a = _year(t_gap, 2014)["cum_cfs_days"].to_numpy()
    b = _year(t_full, 2014)["cum_cfs_days"].to_numpy()
    assert np.all(a <= b + 1e-9)


def test_r9_current_year_elapsed_days_end_at_last_observation():
    df = _frame([2020], current=(2021, 40))
    _, summary = _wyv().water_year_volume_table(df)
    s = _summ(summary, 2021)
    assert s["elapsed_days"] == 40 and s["missing_days"] == 0


# ------------------------------------------------------------------ R8 bands

def _hist_years(n, start=2001):
    return list(range(start, start + n))


def test_r8_bands_are_percentiles_of_cumulative_curves_across_years():
    wys = _hist_years(12)
    k = {wy: i + 1 for i, wy in enumerate(wys)}           # constant flow 1..12
    df = _frame(wys, flow=lambda wy, i: float(k[wy]))
    table, summary = _wyv().water_year_volume_table(df)
    res = _wyv().cumulative_bands(table, current_wy=2099, summary=summary)
    assert res["has_bands"] is True and res["n_years"] == 12
    b = res["bands"].set_index("day_of_wy")
    for d in (1, 100, 365):
        curves = np.array([k[wy] * d for wy in wys], dtype=float)
        assert b.loc[d, "q50"] == pytest.approx(np.percentile(curves, 50))
        assert b.loc[d, "q10"] == pytest.approx(np.percentile(curves, 10))
        assert b.loc[d, "q90"] == pytest.approx(np.percentile(curves, 90))
        assert b.loc[d, "median"] == pytest.approx(b.loc[d, "q50"])


def test_r8_band_columns_follow_default_percentiles():
    from usgs_dashboard.utils.config import DEFAULT_PERCENTILES
    wys = _hist_years(11)
    table, summary = _wyv().water_year_volume_table(_frame(wys))
    res = _wyv().cumulative_bands(table, current_wy=2099, summary=summary)
    for p in DEFAULT_PERCENTILES:
        assert f"q{p}" in res["bands"].columns
    assert "median" in res["bands"].columns


def test_r8_bands_are_ordered_low_to_high():
    rng = np.random.default_rng(7)
    wys = _hist_years(15)
    table, summary = _wyv().water_year_volume_table(
        _frame(wys, flow=lambda wy, i: float(rng.uniform(1, 500))))
    b = _wyv().cumulative_bands(table, current_wy=2099, summary=summary)["bands"]
    assert (b["q10"] <= b["q25"]).all() and (b["q25"] <= b["q50"]).all()
    assert (b["q50"] <= b["q75"]).all() and (b["q75"] <= b["q90"]).all()


def test_r8_current_water_year_is_excluded_from_its_own_bands():
    wys = _hist_years(12)
    df = _frame(wys, flow=lambda wy, i: 10.0, current=(2013, 100))
    # make the current year absurdly large
    df.loc[df["datetime"] >= "2012-10-01", "discharge"] = 1e6
    table, summary = _wyv().water_year_volume_table(df)
    res = _wyv().cumulative_bands(table, current_wy=2013, summary=summary)
    assert res["n_years"] == 12
    b = res["bands"].set_index("day_of_wy")
    assert b.loc[50, "q90"] == pytest.approx(10.0 * 50)


def test_r8_only_completed_years_qualify_even_if_current_not_named():
    # last year in the table is partial; it must not count as a qualifying year
    wys = _hist_years(10)
    df = _frame(wys, current=(2011, 120))
    table, summary = _wyv().water_year_volume_table(df)
    res = _wyv().cumulative_bands(table, current_wy=2011, summary=summary)
    assert res["n_years"] == 10 and res["has_bands"] is True


# ------------------------------------------------------------------ R9 exclusion

def test_r9_year_at_exactly_5pct_missing_is_kept_and_over_5pct_excluded():
    wys = _hist_years(10, start=2002)   # 2002..2011, includes leap WYs 2004, 2008
    ok = _frame(wys)
    # WY2011 (365 days): 18 missing = 4.93% (kept) vs 19 missing = 5.21% (excluded)
    days = pd.date_range("2010-10-01", "2011-09-30")
    kept = ok[~ok["datetime"].isin(days[:18])]
    t, s = _wyv().water_year_volume_table(kept)
    r = _wyv().cumulative_bands(t, current_wy=2099, summary=s)
    assert r["n_years"] == 10 and r["has_bands"] is True
    dropped = ok[~ok["datetime"].isin(days[:19])]
    t, s = _wyv().water_year_volume_table(dropped)
    r = _wyv().cumulative_bands(t, current_wy=2099, summary=s)
    assert r["n_years"] == 9 and r["has_bands"] is False
    assert 2011 in r["excluded_years"]


def test_r9_exclusion_is_logged_with_site_id_and_counts(caplog):
    wys = _hist_years(11)
    df = _frame(wys, drop=pd.date_range("2002-10-01", periods=60))   # WY2003 ~16% missing
    t, s = _wyv().water_year_volume_table(df)
    with caplog.at_level(logging.INFO):
        _wyv().cumulative_bands(t, current_wy=2099, summary=s, site_id="12345678")
    msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    hit = [m for m in msgs if "12345678" in m and "2003" in m]
    assert hit, msgs
    assert any("60" in m for m in hit), hit


# ------------------------------------------------------------------ R11

@pytest.mark.parametrize("n,expected", [(9, False), (10, True), (11, True), (0, False)])
def test_r11_min_years_threshold(n, expected):
    wys = _hist_years(n) if n else []
    df = _frame(wys + [2090], current=None) if n else _frame([2090])
    table, summary = _wyv().water_year_volume_table(df)
    res = _wyv().cumulative_bands(table, current_wy=2090, summary=summary)
    assert res["has_bands"] is expected
    assert res["n_years"] == n
    if not expected:
        assert res["bands"] is None or len(res["bands"]) == 0


def test_r11_gappy_years_do_not_count_toward_minimum():
    wys = _hist_years(12)
    drop = []
    for wy in wys[:3]:
        drop += list(pd.date_range(f"{wy - 1}-10-01", periods=40))
    t, s = _wyv().water_year_volume_table(_frame(wys, drop=drop))
    res = _wyv().cumulative_bands(t, current_wy=2099, summary=s)
    assert res["n_years"] == 9 and res["has_bands"] is False


# ------------------------------------------------------------------ data_manager

@pytest.fixture
def dm(tmp_path):
    with patch("usgs_dashboard.data.data_manager.get_adapter") as ga:
        ga.return_value = MagicMock()
        from usgs_dashboard.data.data_manager import USGSDataManager
        return USGSDataManager(cache_dir=str(tmp_path / "dm"))


def _live_history(unit=None, years=12, current_days=40, flow=100.0):
    """History ending now: `years` complete WYs before the current one + partial current."""
    from usgs_dashboard.utils.water_year_calculator import get_water_year
    cur = get_water_year(pd.Timestamp.now())
    wys = list(range(cur - years, cur))
    return _frame(wys, flow=lambda wy, i: flow, current=(cur, current_days), unit=unit), cur


def _stats_sentinel():
    d = np.arange(1, 367)
    return pd.DataFrame({"day_of_wy": d, "q10": 111.0, "q25": 222.0, "q50": 777.0,
                         "q75": 888.0, "q90": 999.0, "mean": 700.0, "median": 777.0})


def _wire(dm, hist):
    dm.get_streamflow_data = MagicMock(side_effect=lambda *a, **k: hist.copy())
    dm.get_flow_statistics = MagicMock(return_value=_stats_sentinel())


def test_dm_returns_ok_result_with_table_bands_and_gap_summary(dm):
    hist, cur = _live_history()
    _wire(dm, hist)
    out = dm.get_water_year_volume("SITE")
    assert out["status"] == "ok"
    assert out["current_wy"] == cur
    assert out["bands"]["has_bands"] is True
    assert out["current_missing_days"] == 0
    assert {"cum_cfs_days", "daily_cfs_days"} <= set(out["table"].columns)


def test_dm_cms_native_station_volume_is_converted_to_cfs_days(dm):
    hist, cur = _live_history(unit="cms", flow=2.0)
    _wire(dm, hist)
    out = dm.get_water_year_volume("SITE")
    t = out["table"]
    last_full = t[t["water_year"] == cur - 1]
    assert last_full["cum_cfs_days"].iloc[-1] == pytest.approx(
        2.0 * CFS_PER_CMS * len(last_full), rel=1e-6)


def test_r12_daily_bands_are_existing_flow_stats_scaled_not_recomputed(dm):
    hist, _ = _live_history()
    _wire(dm, hist)
    out = dm.get_water_year_volume("SITE")
    # Data are constant 100 cfs; recomputing from data would give 100, not 777.
    db = out["daily_bands"].set_index("day_of_wy")
    # canonical unit is cfs-days: 1 cfs for 1 day = 1 cfs-day, so scale factor is 1
    assert db.loc[10, "q50"] == pytest.approx(777.0)
    assert db.loc[10, "q10"] == pytest.approx(111.0)
    assert db.loc[10, "q90"] == pytest.approx(999.0)


def test_r12_stats_requested_in_cfs_before_scaling(dm):
    hist, _ = _live_history(unit="cms", flow=2.0)
    _wire(dm, hist)
    dm.get_water_year_volume("SITE")
    dm.get_flow_statistics.assert_called()
    c = dm.get_flow_statistics.call_args
    assert "cfs" in c.args or c.kwargs.get("display_unit") == "cfs"


def test_r20_second_call_for_same_site_uses_cache(dm):
    hist, _ = _live_history()
    _wire(dm, hist)
    a = dm.get_water_year_volume("SITE")
    b = dm.get_water_year_volume("SITE")
    assert dm.get_streamflow_data.call_count == 1
    assert a["status"] == b["status"] == "ok"


def test_r20_cache_is_keyed_per_site(dm):
    hist, _ = _live_history()
    _wire(dm, hist)
    dm.get_water_year_volume("AAA")
    dm.get_water_year_volume("BBB")
    assert dm.get_streamflow_data.call_count == 2


def test_r20_cache_expires_after_ttl(dm, monkeypatch):
    hist, _ = _live_history()
    _wire(dm, hist)
    offset = {"v": 0.0}
    real_time, real_mono = time.time, time.monotonic
    monkeypatch.setattr(time, "time", lambda: real_time() + offset["v"])
    monkeypatch.setattr(time, "monotonic", lambda: real_mono() + offset["v"])
    dm.get_water_year_volume("SITE")
    offset["v"] = 10.0
    dm.get_water_year_volume("SITE")
    assert dm.get_streamflow_data.call_count == 1          # inside 5-minute TTL
    offset["v"] = 600.0
    dm.get_water_year_volume("SITE")
    assert dm.get_streamflow_data.call_count == 2          # past TTL


def test_r9_current_year_gap_is_counted_and_logged(dm, caplog):
    hist, cur = _live_history(current_days=40)
    gap = pd.Timestamp(f"{cur - 1}-10-10")
    hist = hist[hist["datetime"] != gap].reset_index(drop=True)
    _wire(dm, hist)
    with caplog.at_level(logging.INFO):
        out = dm.get_water_year_volume("SITE9")
    assert out["current_missing_days"] == 1
    assert any("SITE9" in r.getMessage() for r in caplog.records if r.levelno >= logging.INFO)


def test_r24_empty_history_returns_empty_status_without_raising(dm):
    dm.get_streamflow_data = MagicMock(return_value=pd.DataFrame())
    dm.get_flow_statistics = MagicMock(return_value=pd.DataFrame())
    out = dm.get_water_year_volume("SITE")
    assert out["status"] == "empty"


def test_r24_none_history_returns_empty_status(dm):
    dm.get_streamflow_data = MagicMock(return_value=None)
    assert dm.get_water_year_volume("SITE")["status"] == "empty"


def test_r25_api_error_returns_error_status_without_raising(dm):
    dm.get_streamflow_data = MagicMock(side_effect=ConnectionError("boom"))
    out = dm.get_water_year_volume("SITE")
    assert out["status"] == "error"


def test_r25_error_log_has_site_id_but_no_url_or_token(dm, caplog):
    secret = "SECRETTOKEN123"
    dm.get_streamflow_data = MagicMock(
        side_effect=RuntimeError(f"401 https://api.example/x?token={secret} Bearer {secret}"))
    with caplog.at_level(logging.DEBUG):
        dm.get_water_year_volume("SITE77")
    assert "SITE77" in caplog.text
    assert secret not in caplog.text
    assert "https://" not in caplog.text


def test_r25_errors_are_not_cached(dm):
    dm.get_streamflow_data = MagicMock(side_effect=ConnectionError("boom"))
    dm.get_water_year_volume("SITE")
    hist, _ = _live_history()
    _wire(dm, hist)
    assert dm.get_water_year_volume("SITE")["status"] == "ok"
