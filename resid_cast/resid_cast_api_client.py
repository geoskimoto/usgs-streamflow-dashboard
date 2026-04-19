"""HTTP client for the ResidCast forecast API.

Calls GET /api/v1/stations/{nwrfc_id}/forecasts/?limit=N and returns
predictions in the standard resid_cast format consumed by ResidCastAdapter.
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Maps variant key → human-readable legend label
_LABEL_MAP: dict[str, str] = {
    "xgboost/raw":          "XGBoost",
    "muthre/standalone":    "MUTHRE",
    "lstm/raw/general":     "LSTM (general)",
}


def _variant_key(model_name: str, residual_type: str, is_general: bool) -> str:
    base = f"{model_name}/{residual_type}"
    return f"{base}/general" if is_general else base


def model_label(variant_key: str) -> str:
    return _LABEL_MAP.get(variant_key, variant_key)


class ResidCastApiClient:
    """Fetches ResidCast ML forecasts from the REST API."""

    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {token}"})
        self._timeout = timeout

    def get_forecasts(
        self,
        nwrfc_id: str,
        allowed_variants: list[str],
        num_runs: int = 5,
    ) -> list[dict[str, Any]]:
        """Return forecast runs for a station filtered to allowed_variants.

        Returns a list of dicts:
            run_date   : str  (YYYY-MM-DD derived from issued_at)
            model_label: str
            model_key  : str  (variant key, e.g. "xgboost/raw")
            source     : "resid_cast"
            data       : list[dict]  [{datetime_str, discharge_cfs}, ...]
        """
        url = f"{self._base_url}/api/v1/stations/{nwrfc_id}/forecasts/"
        try:
            resp = self._session.get(
                url, params={"limit": num_runs}, timeout=self._timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("ResidCast API request failed for %s: %s", nwrfc_id, exc)
            return []

        runs: list[dict] = resp.json()
        result = []

        for run in runs:
            for variant in run.get("forecasts", []):
                key = _variant_key(
                    variant["model_name"],
                    variant["residual_type"],
                    variant["is_general"],
                )
                if key not in allowed_variants:
                    continue

                # Use issued_at date as the run_date label
                issued_at = variant.get("issued_at", "")
                run_date = issued_at[:10] if issued_at else str(run.get("run_id", ""))

                data_rows = [
                    {
                        "datetime": p["lead_date"],
                        "discharge_cfs": p["corrected_value_cfs"],
                    }
                    for p in variant.get("predictions", [])
                    if p.get("corrected_value_cfs") is not None
                ]
                if not data_rows:
                    continue

                result.append({
                    "run_date": run_date,
                    "model_label": model_label(key),
                    "model_key": key,
                    "source": "resid_cast",
                    "data": data_rows,
                })

        return result
