from typing import List, Dict, Any, Tuple
from db import get_db
from utils.query import norm_text
from importlib import import_module

# Use your existing munro_coords module
munro_coords = import_module("munro_coords")


def nearest_by_location(location_query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Returns [{name, distance_km}] using munro_coords (geocode + nearest).
    Raises if munro_coords table is empty as per your module.
    """
    df = munro_coords.nearest_munros_from_user_location(location_query, k=k)
    return [
        {"name": r["name"], "distance_km": float(r["distance_km"])}
        for _, r in df.iterrows()
    ]


def _map_names_to_db_rows(named: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    For each {'name', 'distance_km'}, fetch munro id/name/summary/description.
    Tries exact, case-insensitive, and LIKE as fallback.
    """
    if not named:
        return []

    with get_db() as conn:
        # Preload names to support loose matching
        all_rows = conn.execute(
            "SELECT id, name, summary, description FROM munros"
        ).fetchall()
        idx_exact = {r["name"]: dict(r) for r in all_rows}
        idx_loose = {norm_text(r["name"]): dict(r) for r in all_rows}

        out: List[Dict[str, Any]] = []
        for item in named:
            nm = item["name"]
            dist = item["distance_km"]

            row = idx_exact.get(nm)
            if not row:
                row = idx_loose.get(norm_text(nm))
            if not row:
                # Last-chance LIKE
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
    """Mutates rows in-place to add 'tags': [...]"""
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
