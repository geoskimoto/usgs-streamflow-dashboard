#!/usr/bin/env python3
"""
Cache management CLI for the USGS Streamflow Dashboard.

Analogous to Django management commands but for this Dash app.
Rebuilds the per-day-of-water-year statistics cache used by the fast
water year plot path.

Usage
-----
  python manage_cache.py rebuild_stats --all-stations
  python manage_cache.py rebuild_stats --active
  python manage_cache.py rebuild_stats --forecast
  python manage_cache.py rebuild_stats --site 14187500

  python manage_cache.py clear_stats [--site 14187500]

Options (rebuild_stats)
-----------------------
  --all-stations   Rebuild for every station in the configured target states.
  --active         Rebuild only for stations classified as active (data in
                   the last 6 months).
  --forecast       Rebuild only for stations that have NWRFC or ResidCast
                   ML forecast data.
  --site SITE_ID   Rebuild for a single USGS site ID.
  --workers N      Number of parallel worker threads (default: 4).
  --force          Rebuild even when a valid cache already exists.
  --dry-run        Print which stations would be processed; do not fetch
                   data or write cache files.

Options (clear_stats)
---------------------
  --site SITE_ID   Clear cache only for this site. Without --site, clears
                   all cache files.
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Bootstrap: load .env and extend path ──────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / ".env")

from usgs_dashboard.data.stats_cache_manager import (
    STATS_CACHE_DIR,
    _cache_path,
    _current_water_year,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("manage_cache")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_data_manager():
    """Initialise and return a USGSDataManager."""
    from usgs_dashboard.data.data_manager import USGSDataManager
    return USGSDataManager(cache_dir=str(_REPO_ROOT / "data"))


def _load_nwrfc_usgs_ids() -> set:
    """Return the set of USGS station IDs that have NWRFC forecast data."""
    crosswalk_path = _REPO_ROOT / "data" / "nwrfc_usgs_crosswalk.json"
    if not crosswalk_path.exists():
        logger.warning(f"NWRFC crosswalk not found: {crosswalk_path}")
        return set()
    with open(crosswalk_path) as f:
        data = json.load(f)
    return set(data.values())


def _cache_exists_for_current_wy(site_id: str) -> bool:
    """Return True if a valid stats cache file exists for the current water year."""
    return os.path.exists(_cache_path(site_id, _current_water_year()))


def _build_station_list(args, dm) -> list[str]:
    """
    Return the list of site IDs to process based on the CLI flags.

    Loads station metadata once and filters in-memory; does not make
    per-station API calls at this stage.
    """
    if args.site:
        return [args.site]

    logger.info("Loading station list from DataOps…")
    stations_df = dm.load_regional_gauges()

    if stations_df.empty:
        logger.error("No stations returned from DataOps — cannot build station list.")
        return []

    # Normalise site_id column name
    id_col = next(
        (c for c in ("station_number", "site_id", "site_no") if c in stations_df.columns),
        None,
    )
    if id_col is None:
        logger.error("Station DataFrame has no recognisable ID column.")
        return []

    all_ids = stations_df[id_col].dropna().astype(str).tolist()

    if args.all_stations:
        return all_ids

    if args.active:
        if "is_active" in stations_df.columns:
            active_mask = stations_df["is_active"].fillna(False).astype(bool)
            return stations_df.loc[active_mask, id_col].dropna().astype(str).tolist()
        else:
            logger.warning("No 'is_active' column found; falling back to all stations.")
            return all_ids

    if args.forecast:
        nwrfc_ids = _load_nwrfc_usgs_ids()
        resid_cast_ids = dm.get_resid_cast_station_ids()
        forecast_ids = nwrfc_ids | resid_cast_ids
        filtered = [sid for sid in all_ids if sid in forecast_ids]
        logger.info(
            f"Forecast filter: {len(nwrfc_ids)} NWRFC + {len(resid_cast_ids)} ResidCast "
            f"→ {len(filtered)} matching stations"
        )
        return filtered

    logger.error("No station selection flag provided.")
    return []


# ── Rebuild command ────────────────────────────────────────────────────────────

def _rebuild_one(site_id: str, dm, force: bool) -> tuple[str, str, float]:
    """
    Rebuild the stats cache for a single site.

    Returns (site_id, status, elapsed_seconds).
    Status is one of: 'rebuilt', 'skipped', 'error'.
    """
    if not force and _cache_exists_for_current_wy(site_id):
        return site_id, "skipped", 0.0

    t0 = time.perf_counter()
    try:
        stats = dm.get_flow_statistics(site_id)
        elapsed = time.perf_counter() - t0
        if stats.empty:
            return site_id, "error", elapsed
        return site_id, "rebuilt", elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error(f"  [{site_id}] Exception: {exc}")
        return site_id, "error", elapsed


def cmd_rebuild_stats(args):
    """Entry point for the rebuild_stats sub-command."""
    dm = _get_data_manager()
    site_ids = _build_station_list(args, dm)

    if not site_ids:
        logger.error("No stations to process — exiting.")
        sys.exit(1)

    current_wy = _current_water_year()
    logger.info(
        f"\nTarget water year : WY{current_wy}\n"
        f"Stats cache dir   : {STATS_CACHE_DIR}\n"
        f"Stations selected : {len(site_ids)}\n"
        f"Workers           : {args.workers}\n"
        f"Force rebuild     : {args.force}\n"
        f"Dry run           : {args.dry_run}\n"
    )

    if args.dry_run:
        print(f"\n{'─'*60}")
        print(f"DRY RUN — would process {len(site_ids)} station(s):\n")
        for sid in site_ids:
            cached = _cache_exists_for_current_wy(sid)
            action = "skip (cached)" if cached and not args.force else "rebuild"
            print(f"  {sid:<15}  {action}")
        print(f"{'─'*60}\n")
        return

    os.makedirs(STATS_CACHE_DIR, exist_ok=True)

    counters = {"rebuilt": 0, "skipped": 0, "error": 0}
    total = len(site_ids)
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_rebuild_one, sid, dm, args.force): sid for sid in site_ids}
        for i, future in enumerate(as_completed(futures), start=1):
            site_id, status, elapsed = future.result()
            counters[status] += 1
            icon = {"rebuilt": "✅", "skipped": "⏭️ ", "error": "❌"}[status]
            elapsed_str = f"{elapsed:.1f}s" if status != "skipped" else "—"
            print(
                f"  [{i:>4}/{total}]  {icon}  {site_id:<15}  {status:<8}  {elapsed_str}",
                flush=True,
            )

    wall = time.perf_counter() - start_time
    print(f"\n{'─'*60}")
    print(
        f"Done in {wall:.1f}s  |  "
        f"rebuilt={counters['rebuilt']}  "
        f"skipped={counters['skipped']}  "
        f"errors={counters['error']}"
    )
    print(f"{'─'*60}\n")

    if counters["error"] > 0:
        sys.exit(1)


# ── Clear command ──────────────────────────────────────────────────────────────

def cmd_clear_stats(args):
    """Delete stats cache files."""
    cache_dir = Path(STATS_CACHE_DIR)

    if args.site:
        pattern = f"{args.site}_WY*.parquet"
        files = list(cache_dir.glob(pattern))
        if not files:
            print(f"No cache files found for site {args.site}.")
            return
        for f in files:
            f.unlink()
            print(f"Deleted: {f.name}")
    else:
        files = list(cache_dir.glob("*_WY*.parquet"))
        if not files:
            print("No cache files found.")
            return
        confirm = input(f"Delete all {len(files)} cache file(s)? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
        for f in files:
            f.unlink()
            print(f"Deleted: {f.name}")
        print(f"\nRemoved {len(files)} file(s).")


# ── Argument parser ────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_cache.py",
        description="Stats cache management for USGS Streamflow Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── rebuild_stats ──────────────────────────────────────────────────────────
    rebuild = sub.add_parser(
        "rebuild_stats",
        help="Rebuild per-day-of-WY statistics cache",
    )

    group = rebuild.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all-stations",
        action="store_true",
        help="All stations in the configured target states",
    )
    group.add_argument(
        "--active",
        action="store_true",
        help="Only stations classified as active (data in last 6 months)",
    )
    group.add_argument(
        "--forecast",
        action="store_true",
        help="Only stations with NWRFC or ResidCast ML forecast data",
    )
    group.add_argument(
        "--site",
        metavar="SITE_ID",
        help="Single USGS site ID (e.g. 14187500)",
    )

    rebuild.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Parallel worker threads (default: 4)",
    )
    rebuild.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when a valid cache already exists",
    )
    rebuild.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without fetching or writing anything",
    )

    # ── clear_stats ────────────────────────────────────────────────────────────
    clear = sub.add_parser(
        "clear_stats",
        help="Delete stats cache files",
    )
    clear.add_argument(
        "--site",
        metavar="SITE_ID",
        help="Clear only this site's cache (default: clear all)",
    )

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "rebuild_stats":
        cmd_rebuild_stats(args)
    elif args.command == "clear_stats":
        cmd_clear_stats(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
