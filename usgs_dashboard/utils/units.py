"""
Flow-unit helpers (cfs <-> cms). Single source of truth for discharge unit
conversion, labels and axis titles.

Native data keeps its source unit (USGS = cfs, Environment Canada = cms);
conversion happens only at the display boundary. Never write converted values
into the stats cache.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

import pandas as pd

CFS_PER_CMS = 35.3146667  # 1 m^3/s expressed in ft^3/s

_ALIASES = {
    "cfs": "cfs",
    "cms": "cms",
    "m3/s": "cms",
    "m³/s": "cms",
}
_LABELS = {"cfs": "cfs", "cms": "m³/s"}

# Flow-valued columns converted by default in convert_frame.
FLOW_COLUMNS = (
    "discharge", "discharge_cfs",
    "q10", "q25", "q50", "q75", "q90", "mean", "median",
)


def normalize_unit(unit) -> str:
    """Return 'cfs' or 'cms'. None/NaN default to 'cfs'; unknown raises ValueError."""
    if unit is None or (isinstance(unit, float) and math.isnan(unit)):
        return "cfs"
    key = str(unit).strip().lower()
    try:
        return _ALIASES[key]
    except KeyError:
        raise ValueError(f"Unknown flow unit: {unit!r}") from None


def _factor(from_unit, to_unit) -> float:
    src, dst = normalize_unit(from_unit), normalize_unit(to_unit)
    if src == dst:
        return 1.0
    return CFS_PER_CMS if src == "cms" else 1.0 / CFS_PER_CMS


def convert_flow(values, from_unit, to_unit):
    """Convert scalar / ndarray / Series between flow units (NaN preserved)."""
    f = _factor(from_unit, to_unit)
    return values if f == 1.0 and not hasattr(values, "copy") else (
        values.copy() if f == 1.0 else values * f
    )


def unit_label(unit) -> str:
    """Display label: 'cfs' or 'm³/s'."""
    return _LABELS[normalize_unit(unit)]


def axis_title(unit, prefix: str = "Discharge") -> str:
    """Y-axis title, e.g. 'Discharge (m³/s)'."""
    return f"{prefix} ({unit_label(unit)})"


def convert_frame(
    df: pd.DataFrame, to_unit, cols: Optional[Iterable[str]] = None
) -> pd.DataFrame:
    """
    Return a copy of df with flow columns converted into to_unit.

    Each row is converted from its own 'unit' column (cfs if the column is
    absent or null). The 'unit' column of the result is set to to_unit.
    """
    target = normalize_unit(to_unit)
    out = df.copy()
    if cols is None:
        cols = [c for c in FLOW_COLUMNS if c in out.columns]
    else:
        cols = [c for c in cols if c in out.columns]

    if "unit" in out.columns:
        factors = out["unit"].map(lambda u: _factor(u, target)).astype(float)
    else:
        factors = pd.Series(_factor("cfs", target), index=out.index)

    for c in cols:
        out[c] = out[c] * factors
    out["unit"] = target
    return out
