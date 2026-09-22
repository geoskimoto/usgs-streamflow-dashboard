"""Adapter for the blended forecast from model-blender.

Calls GET /api/v1/blended-forecasts/{nwrfc_id}/ and reshapes the flat
per-lead-day response into the same list-of-runs shape ResidCastAdapter and
PrecipRunoffAdapter return, so viz_manager needs no special-casing. Unlike
those two, model-blender exposes only the current best-known blend per
station (not historical runs), so get_forecasts() always returns 0 or 1
entries regardless of num_runs.
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


class BlendedForecastAdapter:
    """Fetches the current blended forecast from model-blender.

    Returns data in the same shape as ResidCastAdapter/PrecipRunoffAdapter:
        [{run_date, model_label, model_key, source, data (DataFrame)}]
    Always 0 or 1 entries (model-blender exposes one current blend per
    station, not historical runs).

    Only stations with ealstm_available: true in resid_cast_stations.json
    are queried -- the same 37-station set precip-runoff-cast covers, which
    is also model-blender's binding constraint for lead days 8-13. Returns
    [] on all failure modes.
    """

    def __init__(self):
        self._config = self._load_config()
        self._api_url = os.environ.get("BLENDED_FORECAST_API_URL", "").rstrip("/")
        self._token = os.environ.get("BLENDED_FORECAST_API_TOKEN", "")

    def _load_config(self) -> dict[str, dict]:
        try:
            with open(_CONFIG_PATH) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load resid_cast_stations.json: %s", exc)
            return {}

    def station_usgs_ids(self) -> set[str]:
        """Return USGS IDs that have a blended forecast available."""
        return {
            uid for uid, cfg in self._config.items()
            if cfg.get("ealstm_available", False)
        }

    def get_forecasts(
        self, usgs_station_id: str, num_runs: int = 5
    ) -> list[dict[str, Any]]:
        """Return the current blended forecast as a single-entry list.

        num_runs is accepted for interface parity with ResidCastAdapter and
        PrecipRunoffAdapter but has no effect -- model-blender's endpoint
        has no pagination/limit concept.

        Returns [] if station not in config, ealstm_available is False,
        API URL not set, or the request fails.
        """
        if not self._api_url:
            return []

        station_cfg = self._config.get(str(usgs_station_id))
        if not station_cfg:
            return []
        if not station_cfg.get("ealstm_available", False):
            return []

        nwrfc_id = station_cfg["nwrfc_id"]
        url = f"{self._api_url}/api/v1/blended-forecasts/{nwrfc_id}/"

        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            rows = resp.json()
        except Exception as exc:
            logger.warning("BlendedForecastAdapter failed for %s: %s", nwrfc_id, exc)
            return []

        if not rows:
            return []

        rows = sorted(rows, key=lambda r: r["lead_day"])

        df = pd.DataFrame({
            "datetime": pd.to_datetime([r["valid_date"] for r in rows]),
            "discharge_cfs": [float(r["value_cfs"]) for r in rows],
        })

        # model-blender's response has no top-level as-of/run_date field --
        # reconstruct it from the earliest lead_day row's valid_date and
        # lead_day (e.g. lead_day=2, valid_date=2026-06-03 -> run_date=2026-06-01).
        first = rows[0]
        run_date = (
            pd.Timestamp(first["valid_date"]) - pd.Timedelta(days=first["lead_day"])
        ).strftime("%Y-%m-%d")

        return [{
            "run_date": run_date,
            "model_label": "Blended",
            "model_key": "blended",
            "source": "model_blender",
            "data": df,
        }]
