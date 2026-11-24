"""Pure helpers for per-station URLs (no Dash imports).

Two URL shapes:
  /station/<site_id>   standalone station page (map + filter rail hidden)
  /?site=<site_id>     map view with that gauge pre-selected (deep link)
"""
from typing import Optional
from urllib.parse import parse_qs, quote, unquote

STATION_PATH_PREFIX = "/station/"


def station_path(site_id) -> str:
    return STATION_PATH_PREFIX + quote(str(site_id), safe="")


def map_view_url(site_id) -> str:
    if site_id is None or not str(site_id).strip():
        return "/"
    return "/?site=" + quote(str(site_id), safe="")


def _station_id_from_path(pathname) -> Optional[str]:
    if not pathname or not pathname.startswith(STATION_PATH_PREFIX):
        return None
    raw = pathname[len(STATION_PATH_PREFIX):]
    if raw.endswith("/"):
        raw = raw[:-1]
    if not raw or "/" in raw:
        return None
    site_id = unquote(raw)
    return site_id if site_id.strip() else None


def parse_station_site_id(pathname, search="") -> Optional[str]:
    """Site id from /station/<id> (preferred) or ?site=<id>; None if neither."""
    from_path = _station_id_from_path(pathname)
    if from_path:
        return from_path
    if search:
        values = parse_qs(search.lstrip("?")).get("site", [])
        for v in values:
            if v.strip():
                return v
    return None


def is_station_page(pathname) -> bool:
    return _station_id_from_path(pathname) is not None
