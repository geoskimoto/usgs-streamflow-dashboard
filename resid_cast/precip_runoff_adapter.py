"""Adapter for EA-LSTM precip-runoff forecasts from ResidCast API.

Calls GET /api/v1/precip-forecasts/{nwrfc_id}/?limit=N and returns
data in the same format as ResidCastAdapter.get_forecasts().
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "resid_cast_stations.json"


class PrecipRunoffAdapter:
    """Fetches EA-LSTM precip-runoff forecasts from the ResidCast API.

    Returns data in the same shape as ResidCastAdapter.get_forecasts():
        [{run_date, model_label, model_key, source, data (DataFrame)}]

    Only stations with ealstm_available: true in resid_cast_stations.json
    are queried. Returns [] on all failure modes.
    """

    def __init__(self):
        self._config = self._load_config()
        self._api_url = (
            os.environ.get("PRECIP_CAST_API_URL")
            or os.environ.get("RESID_CAST_API_URL")
            or ""
        ).rstrip("/")
        self._token = os.environ.get("RESID_CAST_API_TOKEN", "")

    def _load_config(self) -> dict[str, dict]:
        try:
            with open(_CONFIG_PATH) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load resid_cast_stations.json: %s", exc)
            return {}

    def station_usgs_ids(self) -> set[str]:
        """Return USGS IDs that have EA-LSTM forecasts available."""
        return {
            uid for uid, cfg in self._config.items()
            if cfg.get("ealstm_available", False)
        }

    def get_forecasts(
        self, usgs_station_id: str, num_runs: int = 5
    ) -> list[dict[str, Any]]:
        """Return EA-LSTM forecast runs as DataFrames.

        Returns [] if station not in config, ealstm_available is False,
        API URL not set, or request fails.
        """
        if not self._api_url:
            return []

        station_cfg = self._config.get(str(usgs_station_id))
        if not station_cfg:
            return []
        if not station_cfg.get("ealstm_available", False):
            return []

        nwrfc_id = station_cfg["nwrfc_id"]
        url = f"{self._api_url}/api/v1/precip-forecasts/{nwrfc_id}/?limit={num_runs}"

        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            raw_runs = resp.json()
        except Exception as exc:
            logger.warning("PrecipRunoffAdapter failed for %s: %s", nwrfc_id, exc)
            return []

        result = []
        for run in raw_runs:
            preds = run.get("predictions", [])
            if not preds:
                continue
            df = pd.DataFrame({
                "datetime": pd.to_datetime([p["lead_date"] for p in preds]),
                "discharge_cfs": [float(p["predicted_flow_cfs"]) for p in preds],
            })
            result.append({
                "run_date": run.get("issued_at", "")[:10],
                "model_label": "EA-LSTM",
                "model_key": "ealstm/precip_runoff",
                "source": "precip_runoff",
                "data": df,
            })

        return result
