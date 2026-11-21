"""Water-year runoff volume from daily mean discharge (pure functions; no Dash/Plotly).

Canonical unit is cfs-days: a daily-mean discharge of Q cfs is Q cfs-days of volume for
that day. kaf (thousand acre-feet) is a display scale applied at the figure boundary,
the same pattern ``units.py`` uses for cfs/cms. Native cms stations are converted to
cfs through ``units.convert_frame`` before any volume math.

Gap policy (explicit, never silent): a day with no observation contributes no volume and
is not interpolated. Each water year carries a missing-day count; historical years with
more than WYV_MAX_MISSING_FRAC of their days missing are excluded from the percentile
bands, and every exclusion is logged.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from .config import DEFAULT_PERCENTILES, WYV_MAX_MISSING_FRAC, WYV_MIN_YEARS
from .units import convert_frame
from .water_year_calculator import (
    get_water_year,
    get_water_year_date_range,
    get_water_year_length,
)

logger = logging.getLogger(__name__)

CFS_DAY_TO_ACRE_FT = 86400.0 / 43560.0   # 1 cfs-day = 86,400 ft^3 = 1.983471 acre-ft

TABLE_COLUMNS = ["water_year", "day_of_wy", "daily_cfs_days", "cum_cfs_days"]
SUMMARY_COLUMNS = ["water_year", "elapsed_days", "observed_days", "missing_days"]


def cfs_days_to_kaf(cfs_days):
    """Convert cfs-days to thousand acre-feet (scalar, ndarray or Series)."""
    return cfs_days * CFS_DAY_TO_ACRE_FT / 1000.0


def daily_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with ``daily_cfs_days`` (NaN stays NaN).

    ``df`` needs a ``discharge`` column and optionally ``unit`` ('cfs'/'cms' per row).
    """
    out = convert_frame(df, "cfs", cols=["discharge"])
    flow = pd.to_numeric(out["discharge"], errors="coerce")
    out["daily_cfs_days"] = flow.where(np.isfinite(flow))
    return out


def summarize_gaps(table: pd.DataFrame) -> pd.DataFrame:
    """Per-water-year elapsed / observed / missing day counts from a volume table."""
    if table.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    g = table.groupby("water_year")["daily_cfs_days"]
    out = pd.DataFrame({"elapsed_days": g.size(), "observed_days": g.count()})
    out["missing_days"] = out["elapsed_days"] - out["observed_days"]
    return out.reset_index()[SUMMARY_COLUMNS]


def water_year_volume_table(df: pd.DataFrame):
    """Build the per-day volume table and its gap summary.

    Returns ``(table, summary)``. ``table`` has one row per *elapsed* day of each water
    year (Oct 1 .. Sep 30, or .. the last observed date for the final year). Days with
    no observation have NaN ``daily_cfs_days`` and the cumulative volume is carried flat.
    """
    empty = pd.DataFrame(columns=TABLE_COLUMNS)
    if df is None or df.empty:
        return empty, summarize_gaps(empty)

    vol = daily_volume(df)
    dates = pd.to_datetime(vol["datetime"])
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    series = (
        pd.Series(vol["daily_cfs_days"].to_numpy(), index=dates.dt.normalize())
        .dropna()
        .groupby(level=0).first()
        .sort_index()
    )
    if series.empty:
        return empty, summarize_gaps(empty)

    first_wy = get_water_year(series.index[0])
    last_wy = get_water_year(series.index[-1])
    last_obs = series.index[-1]

    parts = []
    for wy in range(first_wy, last_wy + 1):
        start, end = get_water_year_date_range(wy)
        if wy == last_wy:
            end = min(end, last_obs)
        idx = pd.date_range(start, end, freq="D")
        daily = series.reindex(idx)
        parts.append(pd.DataFrame({
            "water_year": wy,
            "day_of_wy": np.arange(1, len(idx) + 1),
            "daily_cfs_days": daily.to_numpy(),
            "cum_cfs_days": daily.fillna(0.0).cumsum().to_numpy(),
        }))
    table = pd.concat(parts, ignore_index=True)
    return table, summarize_gaps(table)


def cumulative_bands(table: pd.DataFrame, current_wy: int,
                     summary: Optional[pd.DataFrame] = None,
                     site_id: Optional[str] = None) -> dict:
    """Percentile bands of cumulative volume per day of water year.

    Only completed, sufficiently observed historical years qualify; ``current_wy`` never
    contributes to its own bands. Returns ``{'bands', 'has_bands', 'n_years',
    'excluded_years'}``; ``bands`` is None unless at least WYV_MIN_YEARS years qualify.
    """
    if summary is None or summary.empty:
        summary = summarize_gaps(table)

    qualifying, excluded = [], []
    for row in summary.itertuples(index=False):
        wy = int(row.water_year)
        if wy == current_wy or row.elapsed_days < get_water_year_length(wy):
            continue
        if row.missing_days / row.elapsed_days > WYV_MAX_MISSING_FRAC:
            excluded.append(wy)
            logger.info(
                "WYV %s: water year %d excluded from bands (%d of %d days missing, %.1f%%)",
                site_id, wy, row.missing_days, row.elapsed_days,
                100.0 * row.missing_days / row.elapsed_days)
            continue
        qualifying.append(wy)

    result = {"bands": None, "has_bands": False, "n_years": len(qualifying),
              "excluded_years": excluded}
    if len(qualifying) < WYV_MIN_YEARS:
        logger.info("WYV %s: %d qualifying water years (< %d); percentile bands omitted",
                    site_id, len(qualifying), WYV_MIN_YEARS)
        return result

    piv = (table[table["water_year"].isin(qualifying)]
           .pivot(index="day_of_wy", columns="water_year", values="cum_cfs_days"))
    piv = piv[piv.notna().sum(axis=1) >= WYV_MIN_YEARS]   # day 366 exists only in leap years
    values = piv.to_numpy()
    bands = pd.DataFrame({"day_of_wy": piv.index.to_numpy()})
    for p in DEFAULT_PERCENTILES:
        bands[f"q{p}"] = np.nanpercentile(values, p, axis=1)
    bands["median"] = bands["q50"]
    result.update(bands=bands, has_bands=True)
    return result
