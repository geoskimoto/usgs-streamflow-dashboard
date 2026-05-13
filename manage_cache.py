#!/usr/bin/env python3
"""
Cache management CLI for the USGS Streamflow Dashboard.

Analogous to Django management commands but for this Dash app.
Manages two caches:
  - stats cache: per-day-of-water-year statistics (parquet, used by fast plot path)
  - plot cache:  pre-rendered Plotly figure JSON (served directly on station click)

Usage
-----
  python manage_cache.py rebuild_stats --all-stations
  python manage_cache.py rebuild_stats --active
  python manage_cache.py rebuild_stats --forecast
  python manage_cache.py rebuild_stats --site 14187500

  python manage_cache.py clear_stats [--site 14187500]

  python manage_cache.py rebuild_plots [--site 14187500] [--workers 4] [--force] [--dry-run]
  python manage_cache.py clear_plots [--site 14187500]

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

Options (rebuild_plots)
-----------------------
  Rebuilds pre-rendered Plotly figure JSON for NWRFC forecast stations.
  --site SITE_ID   Rebuild for a single USGS site ID.
  --workers N      Number of parallel worker threads (default: 4).
  --force          Rebuild even when a valid cache already exists.
  --dry-run        Print which stations would be processed; do not render
                   or write anything.

Options (clear_plots)
---------------------
  --site SITE_ID   Clear cache only for this site. Without --site, clears
                   all plot cache files.
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
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


# ── rebuild_plots helpers ──────────────────────────────────────────────────────

def _rebuild_plot_one(site_id: str, dm, vm, force: bool) -> tuple[str, str, float]:
    """
    Pre-render and cache the fast water-year plot for a single site.

    Returns (site_id, status, elapsed_seconds).
    Status is one of: 'rebuilt', 'skipped', 'error'.
    """
    from usgs_dashboard.data import plot_cache_manager

    if not force and plot_cache_manager.exists(site_id):
        return site_id, "skipped", 0.0

    t0 = time.perf_counter()
    try:
        current_year_data = dm.get_current_year_data(site_id)
        if current_year_data is None or current_year_data.empty:
            logger.warning(f"  [{site_id}] No current year data")
            return site_id, "error", time.perf_counter() - t0

        statistics = dm.get_flow_statistics(site_id)

        forecast_data = None
        try:
            forecast_data = dm.get_forecast_data(site_id, num_days=5)
        except Exception as exc:
            logger.debug(f"  [{site_id}] Forecast fetch skipped: {exc}")

        resid_cast_data = dm.get_resid_cast_forecasts(site_id, num_runs=5)

        fig = vm.create_fast_water_year_plot(
            site_id=site_id,
            current_year_data=current_year_data,
            statistics=statistics,
            forecast_data=forecast_data,
            resid_cast_data=resid_cast_data,
            data_manager=dm,
        )
        plot_cache_manager.save(site_id, fig)
        return site_id, "rebuilt", time.perf_counter() - t0

    except Exception as exc:
        logger.error(f"  [{site_id}] Exception: {exc}")
        return site_id, "error", time.perf_counter() - t0


def cmd_rebuild_plots(args):
    """Entry point for the rebuild_plots sub-command."""
    import argparse as _argparse
    from usgs_dashboard.components.viz_manager import get_visualization_manager
    from usgs_dashboard.data import plot_cache_manager

    dm = _get_data_manager()
    vm = get_visualization_manager()

    # Always filter to NWRFC forecast stations (union with ResidCast)
    if args.site:
        site_ids = [args.site]
    else:
        _forecast_args = _argparse.Namespace(
            site=None,
            all_stations=False,
            active=False,
            forecast=True,
        )
        site_ids = _build_station_list(_forecast_args, dm)

    if not site_ids:
        logger.error("No stations to process — exiting.")
        sys.exit(1)

    logger.info(
        f"\nPlot cache dir    : {plot_cache_manager.PLOT_CACHE_DIR}\n"
        f"Stations selected : {len(site_ids)}\n"
        f"Workers           : {args.workers}\n"
        f"Force rebuild     : {args.force}\n"
        f"Dry run           : {args.dry_run}\n"
    )

    if args.dry_run:
        print(f"\n{'─'*60}")
        print(f"DRY RUN — would process {len(site_ids)} station(s):\n")
        for sid in site_ids:
            cached = plot_cache_manager.exists(sid)
            action = "skip (cached)" if cached and not args.force else "rebuild"
            print(f"  {sid:<15}  {action}")
        print(f"{'─'*60}\n")
        return

    os.makedirs(plot_cache_manager.PLOT_CACHE_DIR, exist_ok=True)

    counters = {"rebuilt": 0, "skipped": 0, "error": 0}
    total = len(site_ids)
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_rebuild_plot_one, sid, dm, vm, args.force): sid
            for sid in site_ids
        }
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


def cmd_clear_plots(args):
    """Delete plot cache files."""
    from usgs_dashboard.data import plot_cache_manager

    cache_dir = Path(plot_cache_manager.PLOT_CACHE_DIR)

    if not cache_dir.exists():
        print("Plot cache directory does not exist — nothing to clear.")
        return

    if args.site:
        files = list(cache_dir.glob(f"{args.site}_WY*"))
        if not files:
            print(f"No plot cache files found for site {args.site}.")
            return
        for f in files:
            f.unlink()
            print(f"Deleted: {f.name}")
    else:
        files = list(cache_dir.glob("*_WY*"))
        if not files:
            print("No plot cache files found.")
            return
        confirm = input(f"Delete all {len(files)} plot cache file(s)? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
        for f in files:
            f.unlink()
            print(f"Deleted: {f.name}")
        print(f"\nRemoved {len(files)} file(s).")


# ── rebuild_pngs helpers ──────────────────────────────────────────────────────

def _decode_binary_array(raw_val):
    """
    Decode a Plotly binary-encoded array (dict with 'bdata'/'dtype') into a list.
    Returns the original value unchanged if it is not a binary dict.
    """
    import base64, struct
    if not isinstance(raw_val, dict) or 'bdata' not in raw_val:
        return raw_val
    dtype = raw_val.get('dtype', 'f8')
    fmt_map = {'i1': 'b', 'u1': 'B', 'i2': 'h', 'u2': 'H',
               'i4': 'i', 'u4': 'I', 'i8': 'q', 'u8': 'Q',
               'f4': 'f', 'f8': 'd'}
    fmt = fmt_map.get(dtype, 'd')
    size = struct.calcsize(fmt)
    raw = base64.b64decode(raw_val['bdata'])
    n = len(raw) // size
    return struct.unpack(f'{n}{fmt}', raw[:n * size])


def _find_y_max_in_window(fig, x_min: int, x_max: int) -> float:
    """
    Scan all traces and return the max y value where x falls within [x_min, x_max].
    x values are day-of-water-year integers (1–366).
    Handles both plain lists and Plotly binary-encoded arrays.
    """
    y_max = 0.0
    for trace in fig.data:
        xs_raw = trace.x
        ys_raw = trace.y
        if xs_raw is None or ys_raw is None:
            continue
        try:
            xs = _decode_binary_array(xs_raw)
            ys = _decode_binary_array(ys_raw)
            for x_val, y_val in zip(xs, ys):
                if x_val is None or y_val is None:
                    continue
                try:
                    if x_min <= int(x_val) <= x_max:
                        y_max = max(y_max, float(y_val))
                except (TypeError, ValueError):
                    continue
        except Exception:
            continue
    return y_max


def _rebuild_png_one(site_id: str, force: bool) -> tuple[str, str, float]:
    """
    Generate and cache a hover PNG for a single site from its JSON plot cache.

    Returns (site_id, status, elapsed_seconds).
    Status is one of: 'rebuilt', 'skipped', 'error', 'no_json'.
    """
    import plotly.graph_objects as go
    from usgs_dashboard.data import plot_cache_manager
    from usgs_dashboard.data import png_cache_manager

    if not force and png_cache_manager.exists(site_id):
        return site_id, "skipped", 0.0

    if not plot_cache_manager.exists(site_id):
        return site_id, "no_json", 0.0

    t0 = time.perf_counter()
    try:
        fig_dict, _ = plot_cache_manager.get(site_id)
        if fig_dict is None:
            return site_id, "error", time.perf_counter() - t0

        fig = go.Figure(fig_dict)

        # Compute today as day-of-water-year (1=Oct 1 … 366=Sep 30).
        # The stored figure uses a linear integer x-axis, not dates.
        today = datetime.now()
        wy_start_year = today.year - 1 if today.month < 10 else today.year
        wy_start = datetime(wy_start_year, 10, 1)
        wy_end = datetime(wy_start_year + 1, 9, 30)
        wy_length = (wy_end - wy_start).days + 1  # 365 or 366 depending on leap year
        doy_today = (today - wy_start).days + 1
        doy_min = max(1, doy_today - 30)
        doy_max = min(wy_length, doy_today + 30)

        y_max = _find_y_max_in_window(fig, doy_min, doy_max)
        y_ceiling = max(y_max * 1.10, 100.0)  # floor 100 cfs so axis isn't empty

        fig.update_layout(
            xaxis=dict(
                range=[doy_min, doy_max],
                autorange=False,
                tickvals=None,   # clear stored full-year ticks; Plotly auto-generates
                ticktext=None,
                rangeslider=dict(visible=False),
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                color="#cccccc",
                tickfont=dict(color="#cccccc", size=10),
                linecolor="#444444",
            ),
            yaxis=dict(
                range=[0, y_ceiling],
                autorange=False,
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                title=dict(text="Flow (cfs)", font=dict(size=10, color="#cccccc")),
                color="#cccccc",
                tickfont=dict(color="#cccccc", size=10),
                linecolor="#444444",
            ),
            showlegend=False,
            title=None,
            margin=dict(t=8, b=36, l=58, r=8),
            height=220,
            width=400,
            updatemenus=[],
            annotations=[],
            shapes=[
                s for s in (fig.layout.shapes or [])
                if not (getattr(s, "type", None) == "line" and getattr(s, "x0", None) == getattr(s, "x1", None))
            ],
            plot_bgcolor="#2d2d2d",
            paper_bgcolor="#252525",
        )

        ok = png_cache_manager.save(site_id, fig)
        status = "rebuilt" if ok else "error"
        return site_id, status, time.perf_counter() - t0

    except Exception as exc:
        logger.error(f"  [{site_id}] PNG generation failed: {exc}")
        return site_id, "error", time.perf_counter() - t0


def cmd_rebuild_pngs(args):
    """Entry point for the rebuild_pngs sub-command."""
    from usgs_dashboard.data import plot_cache_manager
    from usgs_dashboard.data import png_cache_manager

    if args.site:
        site_ids = [args.site]
    else:
        site_ids = plot_cache_manager.list_cached()

    if not site_ids:
        logger.error("No stations with JSON plot cache found — run rebuild_plots first.")
        sys.exit(1)

    logger.info(
        f"\nPNG cache dir     : {png_cache_manager.PNG_CACHE_DIR}\n"
        f"Stations selected : {len(site_ids)}\n"
        f"Workers           : {args.workers}\n"
        f"Force rebuild     : {args.force}\n"
        f"Dry run           : {args.dry_run}\n"
    )

    if args.dry_run:
        print(f"\n{'─'*60}")
        print(f"DRY RUN — would process {len(site_ids)} station(s):\n")
        for sid in site_ids:
            cached = png_cache_manager.exists(sid)
            action = "skip (cached)" if cached and not args.force else "rebuild"
            print(f"  {sid:<15}  {action}")
        print(f"{'─'*60}\n")
        return

    os.makedirs(png_cache_manager.PNG_CACHE_DIR, exist_ok=True)

    counters = {"rebuilt": 0, "skipped": 0, "error": 0, "no_json": 0}
    total = len(site_ids)
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_rebuild_png_one, sid, args.force): sid for sid in site_ids}
        for i, future in enumerate(as_completed(futures), start=1):
            site_id, status, elapsed = future.result()
            counters[status] = counters.get(status, 0) + 1
            icon = {"rebuilt": "✅", "skipped": "⏭️ ", "error": "❌", "no_json": "⚠️ "}[status]
            elapsed_str = f"{elapsed:.1f}s" if status not in ("skipped", "no_json") else "—"
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
        f"no_json={counters['no_json']}  "
        f"errors={counters['error']}"
    )
    print(f"{'─'*60}\n")

    if counters["error"] > 0:
        sys.exit(1)


def cmd_clear_pngs(args):
    """Delete PNG cache files."""
    from usgs_dashboard.data import png_cache_manager

    cache_dir = Path(png_cache_manager.PNG_CACHE_DIR)
    if not cache_dir.exists():
        print("PNG cache directory does not exist — nothing to clear.")
        return

    if args.site:
        files = list(cache_dir.glob(f"{args.site}_WY*.png"))
        if not files:
            print(f"No PNG cache files found for site {args.site}.")
            return
        for f in files:
            f.unlink()
            print(f"Deleted: {f.name}")
    else:
        files = list(cache_dir.glob("*_WY*.png"))
        if not files:
            print("No PNG cache files found.")
            return
        confirm = input(f"Delete all {len(files)} PNG file(s)? [y/N] ").strip().lower()
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

    # ── rebuild_plots ──────────────────────────────────────────────────────────
    rebuild_plots = sub.add_parser(
        "rebuild_plots",
        help="Pre-render water-year plot figures for NWRFC forecast stations",
    )
    rebuild_plots.add_argument(
        "--site",
        metavar="SITE_ID",
        help="Single USGS site ID (default: all NWRFC forecast stations)",
    )
    rebuild_plots.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Parallel worker threads (default: 4)",
    )
    rebuild_plots.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when a valid cache already exists",
    )
    rebuild_plots.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without rendering or writing anything",
    )

    # ── clear_plots ────────────────────────────────────────────────────────────
    clear_plots = sub.add_parser(
        "clear_plots",
        help="Delete plot cache files",
    )
    clear_plots.add_argument(
        "--site",
        metavar="SITE_ID",
        help="Clear only this site's cache (default: clear all)",
    )

    # ── rebuild_pngs ───────────────────────────────────────────────────────────
    rebuild_pngs = sub.add_parser(
        "rebuild_pngs",
        help="Generate hover PNG thumbnails from existing JSON plot cache",
    )
    rebuild_pngs.add_argument(
        "--site", metavar="SITE_ID",
        help="Single USGS site ID (default: all JSON-cached stations)",
    )
    rebuild_pngs.add_argument(
        "--workers", type=int, default=4, metavar="N",
        help="Parallel worker threads (default: 4)",
    )
    rebuild_pngs.add_argument("--force", action="store_true",
        help="Rebuild even when a valid PNG already exists")
    rebuild_pngs.add_argument("--dry-run", action="store_true",
        help="Print what would happen without writing anything")

    # ── clear_pngs ─────────────────────────────────────────────────────────────
    clear_pngs = sub.add_parser("clear_pngs", help="Delete PNG cache files")
    clear_pngs.add_argument("--site", metavar="SITE_ID",
        help="Clear only this site's PNG (default: clear all)")

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "rebuild_stats":
        cmd_rebuild_stats(args)
    elif args.command == "clear_stats":
        cmd_clear_stats(args)
    elif args.command == "rebuild_plots":
        cmd_rebuild_plots(args)
    elif args.command == "clear_plots":
        cmd_clear_plots(args)
    elif args.command == "rebuild_pngs":
        cmd_rebuild_pngs(args)
    elif args.command == "clear_pngs":
        cmd_clear_pngs(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
