"""Direct PostgreSQL client for ResidCast forecast data.

Queries the resid-cast forecast_predictions table via SQLAlchemy using
RESID_CAST_DB_URL. Used when RESID_CAST_USE_API=false (same-server deployment).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .resid_cast_api_client import _variant_key, model_label

logger = logging.getLogger(__name__)

_FORECASTS_QUERY = text("""
    WITH ranked_runs AS (
        SELECT DISTINCT fp.forecast_run_id,
               ROW_NUMBER() OVER (ORDER BY fp.forecast_run_id DESC) AS rn
        FROM   forecast_predictions fp
        JOIN   stations s ON s.id = fp.station_id
        WHERE  s.nwrfc_id = :nwrfc_id
    ),
    recent_runs AS (
        SELECT forecast_run_id FROM ranked_runs WHERE rn <= :num_runs
    )
    SELECT
        fr.id          AS run_id,
        fr.status      AS run_status,
        ma.model_name,
        ma.residual_type,
        ma.is_general,
        fp.issued_at,
        fp.lead_date,
        fp.corrected_value_cfs
    FROM forecast_predictions fp
    JOIN forecast_runs   fr ON fr.id  = fp.forecast_run_id
    JOIN model_artifacts ma ON ma.id  = fp.artifact_id
    JOIN stations        s  ON s.id   = fp.station_id
    WHERE s.nwrfc_id = :nwrfc_id
      AND fp.forecast_run_id IN (SELECT forecast_run_id FROM recent_runs)
    ORDER BY fp.forecast_run_id DESC, ma.id, fp.lead_day
""")


class ResidCastDbClient:
    """Fetches ResidCast ML forecasts directly from PostgreSQL."""

    def __init__(self, db_url: str):
        engine = create_engine(db_url)
        self._Session = sessionmaker(bind=engine)

    def get_forecasts(
        self,
        nwrfc_id: str,
        allowed_variants: list[str],
        num_runs: int = 5,
    ) -> list[dict[str, Any]]:
        """Return forecast runs for a station filtered to allowed_variants.

        Returns the same structure as ResidCastApiClient.get_forecasts().
        """
        try:
            session = self._Session()
            rows = session.execute(
                _FORECASTS_QUERY,
                {"nwrfc_id": nwrfc_id.upper(), "num_runs": num_runs},
            ).fetchall()
            session.close()
        except Exception as exc:
            logger.warning("ResidCast DB query failed for %s: %s", nwrfc_id, exc)
            return []

        # Group rows by (run_id, variant_key)
        groups: dict[tuple, dict] = {}
        for row in rows:
            key = _variant_key(row.model_name, row.residual_type, row.is_general)
            if key not in allowed_variants:
                continue

            group_key = (row.run_id, key)
            if group_key not in groups:
                issued_at = row.issued_at
                if isinstance(issued_at, datetime):
                    run_date = issued_at.strftime("%Y-%m-%d")
                else:
                    run_date = str(issued_at)[:10]

                groups[group_key] = {
                    "run_date": run_date,
                    "model_label": model_label(key),
                    "model_key": key,
                    "source": "resid_cast",
                    "data": [],
                }

            if row.corrected_value_cfs is not None:
                groups[group_key]["data"].append({
                    "datetime": row.lead_date,
                    "discharge_cfs": row.corrected_value_cfs,
                })

        return [entry for entry in groups.values() if entry["data"]]
