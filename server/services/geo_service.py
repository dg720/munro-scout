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

    # Handful of helpful aliases (expand as needed)
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
    g, rate_geocode = munro_coords._nominatim_geocoder()
    for candidate in _candidate_location_queries(location_query):
        try:
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
    - If not in Scotland, return error via exception
    - Otherwise compute nearest via coords table
    """
    res = geocode_scotland_first(location_query)
    if not res:
        raise ValueError(
            "Location not recognised in Scotland. Try a more specific place (e.g. 'Glen Coe, Scotland')."
        )
    lat, lon, resolved = res
    logger.info(f"[geo] using resolved location '{resolved}'")

    # Use the coords table on the point we validated
    df = munro_coords.nearest_munros_to_point(lat, lon, k=k)
    named = [
        {"name": r["name"], "distance_km": float(r["distance_km"])}
        for _, r in df.iterrows()
    ]
    return named


def _map_names_to_db_rows(named: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not named:
        return []
    with get_db() as conn:
        all_rows = conn.execute(
            "SELECT id, name, summary, description FROM munros"
        ).fetchall()
        idx_exact = {r["name"]: dict(r) for r in all_rows}
        idx_loose = {norm_text(r["name"]): dict(r) for r in all_rows}

        out: List[Dict[str, Any]] = []
        for item in named:
            nm = item["name"]
            dist = item["distance_km"]

            row = idx_exact.get(nm) or idx_loose.get(norm_text(nm))
            if not row:
                got = conn.execute(
                    "SELECT id, name, summary, description FROM munros WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                    (f"%{nm}%",),
                ).fetchone()
                row = dict(got) if got else None

            if row:
                out.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "summary": row.get("summary"),
                        "description": row.get("description") or "",
                        "distance_km": dist,
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
