from typing import List, Dict, Any, Tuple, Optional
import logging
from importlib import import_module
from db import get_db
from utils.query import norm_text

logger = logging.getLogger("geo_service")
munro_coords = import_module("munro_coords")  # uses your existing module objects

# Use the same bbox as your coords builder
SCOTLAND_BBOX = getattr(munro_coords, "SCOTLAND_BBOX", (54.5, -8.5, 60.9, -0.5))


def _within_bbox(lat: float, lon: float, bbox=SCOTLAND_BBOX) -> bool:
    s, w, n, e = bbox
    return (s <= lat <= n) and (w <= lon <= e)


def _candidate_location_queries(q: str) -> List[str]:
    """
    Build a small list of geocode queries biased to Scotland, plus alias fixes.
    """
    base = (q or "").strip()
    if not base:
        return []

    lower = base.lower()
    variants = [base]

    # Helpful aliases (expand as needed)
    if lower == "glencoe":
        variants.append("Glen Coe")
    if lower == "skye":
        variants.append("Isle of Skye")
    if lower == "ben nevis":
        variants.append("Fort William")

    # Prefer Scotland variants first
    out: List[str] = []
    seen = set()
    for v in variants:
        for aug in (f"{v}, Scotland", f"{v}, Scotland, UK", v):
            key = aug.lower().strip()
            if key not in seen:
                seen.add(key)
                out.append(aug)
    return out


def geocode_scotland_first(location_query: str) -> Optional[Tuple[float, float, str]]:
    """
    Try to geocode, insisting results are inside the Scotland bbox.
    Returns (lat, lon, resolved_query) or None.
    """
    _, rate_geocode = munro_coords._nominatim_geocoder()
    for candidate in _candidate_location_queries(location_query):
        try:
            # country_codes=gb gives a GB bias; bbox check enforces Scotland specifically
            loc = rate_geocode(candidate, exactly_one=True, country_codes="gb")
        except Exception:
            loc = None
        if not loc:
            logger.info(f"[geo] no hit for '{candidate}'")
            continue
        lat, lon = float(loc.latitude), float(loc.longitude)
        inside = _within_bbox(lat, lon)
        logger.info(
            f"[geo] '{candidate}' -> ({lat:.5f},{lon:.5f}) | in_scotland={inside}"
        )
        if inside:
            return lat, lon, candidate
    return None


def nearest_by_location(location_query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Strict Scotland path:
    - Geocode with Scotland bias and bbox check
    - If not in Scotland, raise ValueError
    - Otherwise compute nearest via coords table
    """
    res = geocode_scotland_first(location_query)
    if not res:
        raise ValueError(
            "Location not recognised in Scotland. Try a more specific place (e.g. 'Glen Coe, Scotland')."
        )
    lat, lon, resolved = res
    logger.info(f"[geo] using resolved location '{resolved}'")

    # Use the coords table on the validated point
    df = munro_coords.nearest_munros_to_point(lat, lon, k=max(1, int(k or 20)))
    named = [
        {"name": r["name"], "distance_km": float(r["distance_km"])}
        for _, r in df.iterrows()
    ]
    return named


# -------- DB mapping helpers (carry route_distance/route_time if available) --------

_HAS_DISTANCE: Optional[bool] = None
_HAS_TIME: Optional[bool] = None


def _ensure_schema_flags() -> None:
    """Cache whether munros table has distance/time columns."""
    global _HAS_DISTANCE, _HAS_TIME
    if _HAS_DISTANCE is not None and _HAS_TIME is not None:
        return
    try:
        with get_db() as conn:
            cols = [
                r["name"] for r in conn.execute("PRAGMA table_info(munros)").fetchall()
            ]
        _HAS_DISTANCE = "distance" in cols
        _HAS_TIME = "time" in cols
    except Exception:
        _HAS_DISTANCE = False
        _HAS_TIME = False


def _select_row(conn, name_like: Optional[str] = None, exact: Optional[str] = None):
    """
    Fetch a single row by exact name or LIKE name, selecting optional distance/time if present.
    Returns a sqlite Row or None.
    """
    _ensure_schema_flags()
    cols = ["id", "name", "summary", "description"]
    if _HAS_DISTANCE:
        cols.append("distance")
    if _HAS_TIME:
        cols.append("time")
    col_sql = ", ".join(f"m.{c}" for c in cols)
    if exact is not None:
        return conn.execute(
            f"SELECT {col_sql} FROM munros m WHERE m.name = ? LIMIT 1", (exact,)
        ).fetchone()
    if name_like is not None:
        return conn.execute(
            f"SELECT {col_sql} FROM munros m WHERE m.name LIKE ? COLLATE NOCASE LIMIT 1",
            (f"%{name_like}%",),
        ).fetchone()
    return None


def _map_names_to_db_rows(named: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not named:
        return []
    with get_db() as conn:
        # Preload for fast exact/loose lookups
        _ensure_schema_flags()
        base_cols = ["id", "name", "summary", "description"]
        if _HAS_DISTANCE:
            base_cols.append("distance")
        if _HAS_TIME:
            base_cols.append("time")
        col_sql = ", ".join(base_cols)

        all_rows = conn.execute(f"SELECT {col_sql} FROM munros").fetchall()
        # Convert to dicts for Python-side indexing
        all_dicts = [dict(r) for r in all_rows]
        idx_exact = {r["name"]: r for r in all_dicts}
        idx_loose = {norm_text(r["name"]): r for r in all_dicts}

        out: List[Dict[str, Any]] = []
        for item in named:
            nm = item["name"]
            dist_user = item["distance_km"]

            row = idx_exact.get(nm) or idx_loose.get(norm_text(nm))
            if row is None:
                got = _select_row(conn, name_like=nm)
                row = dict(got) if got else None

            if row:
                out.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "summary": row.get("summary"),
                        "description": row.get("description") or "",
                        "distance_km": dist_user,  # distance from user location (for ranking)
                        "route_distance": row.get(
                            "distance"
                        ),  # route length from DB (km) if column exists
                        "route_time": row.get(
                            "time"
                        ),  # route time from DB (hours) if column exists
                    }
                )
    return out


def attach_tags(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    ids = [r["id"] for r in rows]
    with get_db() as conn:
        tag_rows = conn.execute(
            f"SELECT munro_id, tag FROM munro_tags WHERE munro_id IN ({','.join('?' for _ in ids)})",
            ids,
        ).fetchall()
    tmap: Dict[int, List[str]] = {}
    for tr in tag_rows:
        tmap.setdefault(tr["munro_id"], []).append(tr["tag"])
    for r in rows:
        r["tags"] = sorted(tmap.get(r["id"], []))
