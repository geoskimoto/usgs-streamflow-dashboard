"""Unified ResidCast adapter.

Dispatches to either the API client or the DB client based on
RESID_CAST_USE_API, loads the station/model config, and returns DataFrames
in the format consumed by viz_manager._add_forecast_overlay().
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "resid_cast_stations.json"


def _load_config() -> dict[str, dict]:
    """Return {usgs_id: {nwrfc_id, models}} from the station config file."""
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load resid_cast_stations.json: %s", exc)
        return {}


def _rows_to_df(data_rows: list[dict]) -> pd.DataFrame:
    """Convert [{datetime, discharge_cfs}] to a typed DataFrame."""
    if not data_rows:
        return pd.DataFrame(columns=["datetime", "discharge_cfs"])
    df = pd.DataFrame(data_rows)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=False)
    df["discharge_cfs"] = pd.to_numeric(df["discharge_cfs"], errors="coerce")
    return df.dropna(subset=["discharge_cfs"])


class ResidCastAdapter:
    """Single entry point for ResidCast forecast data.

    Usage:
        adapter = ResidCastAdapter()
        runs = adapter.get_forecasts("14187500", num_runs=5)
        # runs: List[Dict] with keys run_date, model_label, model_key, source, data (DataFrame)

        station_ids = adapter.station_usgs_ids()
        # station_ids: set of USGS IDs that have ResidCast forecasts
    """

    def __init__(self):
        self._config: dict[str, dict] = _load_config()
        self._client = self._build_client()

    def _build_client(self):
        use_api = os.environ.get("RESID_CAST_USE_API", "false").lower() == "true"
        if use_api:
            from .resid_cast_api_client import ResidCastApiClient
            api_url = os.environ.get("RESID_CAST_API_URL", "").rstrip("/")
            token = os.environ.get("RESID_CAST_API_TOKEN", "")
            if not api_url:
                logger.error("RESID_CAST_API_URL is not set; ResidCast API unavailable")
                return None
            return ResidCastApiClient(base_url=api_url, token=token)
        else:
            from .resid_cast_db_client import ResidCastDbClient
            db_url = os.environ.get("RESID_CAST_DB_URL", "")
            if not db_url:
                logger.error("RESID_CAST_DB_URL is not set; ResidCast DB unavailable")
                return None
            return ResidCastDbClient(db_url=db_url)

    def station_usgs_ids(self) -> set[str]:
        """Return all USGS station IDs covered by the ResidCast config."""
        return set(self._config.keys())

    def get_forecasts(
        self, usgs_station_id: str, num_runs: int = 5
    ) -> list[dict[str, Any]]:
        """Return forecast runs for a USGS station as DataFrames.

        Each entry in the returned list:
            run_date   : str  (YYYY-MM-DD)
            model_label: str  (e.g. "XGBoost")
            model_key  : str  (e.g. "xgboost/raw")
            source     : "resid_cast"
            data       : pd.DataFrame  columns=['datetime', 'discharge_cfs']

        Returns [] if the station has no ResidCast config or no data.
        """
        if self._client is None:
            return []

        station_cfg = self._config.get(str(usgs_station_id))
        if not station_cfg:
            return []

        nwrfc_id = station_cfg["nwrfc_id"]
        allowed_variants: list[str] = station_cfg.get("models", [])

        raw = self._client.get_forecasts(
            nwrfc_id=nwrfc_id,
            allowed_variants=allowed_variants,
            num_runs=num_runs,
        )

        result = []
        for entry in raw:
            df = _rows_to_df(entry["data"])
            if df.empty:
                continue
            result.append({
                "run_date": entry["run_date"],
                "model_label": entry["model_label"],
                "model_key": entry["model_key"],
                "source": "resid_cast",
                "data": df,
            })

        return result
