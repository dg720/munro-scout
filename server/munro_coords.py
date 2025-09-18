# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import re
import sqlite3
import time
from datetime import datetime
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Optional Overpass fallback
try:
    import overpy

    OVERPY_AVAILABLE = True
except Exception:
    OVERPY_AVAILABLE = False

# ------------------------- Config -------------------------

DB_PATH = os.environ.get("MUNRO_DB", "db.sqlite")
JSON_PATH = os.environ.get("MUNRO_JSON", "munro_descriptions.json")

# Bounding box for Scotland (south, west, north, east)
SCOTLAND_BBOX = (54.5, -8.5, 60.9, -0.5)

# Respectful values; you can tweak max workers if you have your own Nominatim or are okay with slower fallback
MAX_WORKERS = int(os.environ.get("MUNRO_GEOCODE_WORKERS", "3"))

NOMINATIM_USER_AGENT = os.environ.get(
    "NOMINATIM_UA", "munro-coords-app (contact@example.com)"
)

_print_lock = Lock()  # keep logs tidy across threads

# ------------------------- DB helpers -------------------------


def _ensure_conn() -> sqlite3.Connection:
    """Open a SQLite connection with pragmatic performance pragmas applied."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the coordinate cache table and indexes if needed."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS munro_coords (
            name TEXT PRIMARY KEY,
            lat  REAL NOT NULL,
            lon  REAL NOT NULL,
            source TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_munro_coords_latlon ON munro_coords(lat, lon)"
    )
    conn.commit()


# ------------------------- Loading names -------------------------


def load_munro_names(source: str = "auto") -> List[str]:
    """Load a deduplicated list of Munro names from JSON or SQLite storage."""
    names = []
    src = source.lower()
    if src == "auto":
        src = "sqlite" if os.path.exists(DB_PATH) else "json"

    if src == "json":
        df = pd.read_json(JSON_PATH, orient="records")
        if "name" not in df.columns:
            raise ValueError("JSON must contain a 'name' field for each munro.")
        names = df["name"].dropna().astype(str).str.strip().tolist()

    elif src == "sqlite":
        conn = _ensure_conn()
        try:
            for table in ("munros", "munro_descriptions", "munro"):
                try:
                    df = pd.read_sql_query(f"SELECT name FROM {table}", conn)
                    if "name" in df.columns and len(df):
                        names.extend(
                            df["name"].dropna().astype(str).str.strip().tolist()
                        )
                        break
                except Exception:
                    continue
            if not names:
                raise ValueError(
                    "Could not find a table with a 'name' column (tried munros/munro_descriptions/munro)."
                )
        finally:
            conn.close()
    else:
        raise ValueError("source must be 'json', 'sqlite', or 'auto'.")

    # de-dupe preserve order
    seen, ordered = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


# ------------------------- Helpers -------------------------


def _within_bbox(lat: float, lon: float, bbox) -> bool:
    """Return True when a coordinate falls inside the provided bounding box."""
    s, w, n, e = bbox
    return (s <= lat <= n) and (w <= lon <= e)


def sanitize_name(name: str) -> str:
    """Strip extra qualifiers that confuse geocoders while retaining identity."""
    # remove bracketed region qualifiers, e.g. "Stob Binnein (Loch Lomond)"
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    # remove trailing comma segments like ", Skye"
    base = re.sub(r",\s*[^,]+$", "", base).strip()
    return base or name.strip()


# ------------------------- Geocoders -------------------------


def _nominatim_geocoder():
    """Return a Nominatim client plus a rate-limited geocode callable."""
    g = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=10)
    # ≥1s delay per thread; Nominatim is strict. Keep workers low.
    rate_geocode = RateLimiter(
        g.geocode, min_delay_seconds=1, max_retries=2, error_wait_seconds=2
    )
    return g, rate_geocode


def geocode_via_nominatim(name: str, rate_geocode) -> Optional[Tuple[float, float]]:
    """Attempt to geocode a Munro using Nominatim with Scotland-biased queries."""
    clean = sanitize_name(name)
    candidates = [name]
    if clean != name:
        candidates.append(clean)

    # enrich with hints for mountainous places
    variants = []
    for c in candidates:
        variants.extend(
            [f"{c} Munro, Scotland", f"{c} peak, Scotland", f"{c}, Scotland"]
        )

    seen = set()
    for q in variants:
        if q in seen:
            continue
        seen.add(q)
        try:
            loc = rate_geocode(q, addressdetails=False, exactly_one=True)
        except Exception:
            loc = None
        if loc:
            lat, lon = float(loc.latitude), float(loc.longitude)
            if _within_bbox(lat, lon, SCOTLAND_BBOX):
                return lat, lon
    return None


def geocode_via_overpass(name: str) -> Optional[Tuple[float, float]]:
    """Fallback to Overpass to geocode peak features when Nominatim fails."""
    if not OVERPY_AVAILABLE:
        return None
    api = overpy.Overpass()
    clean = sanitize_name(name)

    s, w, n, e = SCOTLAND_BBOX
    # Search for exact or case-insensitive matches of name
    # Try original first, then sanitized base.
    names_to_try = [name]
    if clean != name:
        names_to_try.append(clean)

    for nm in names_to_try:
        q = f"""
        [out:json][timeout:25];
        (
          node["natural"="peak"]["name"="{nm}"]({s},{w},{n},{e});
          node["natural"="peak"]["name:en"="{nm}"]({s},{w},{n},{e});
        );
        out body;
        """
        try:
            r = api.query(q)
        except Exception:
            r = None

        if r and r.nodes:
            # Prefer node with highest elevation if available
            best = None
            best_ele = -1
            for node in r.nodes:
                ele = node.tags.get("ele")
                try:
                    ele_f = float(ele) if ele is not None else -1
                except Exception:
                    ele_f = -1
                if ele_f > best_ele:
                    best_ele = ele_f
                    best = node
            if best:
                return float(best.lat), float(best.lon)

    return None


# ------------------------- Build / Update (now parallel) -------------------------


def _process_one(
    i: int, total: int, name: str
) -> Optional[Tuple[str, float, float, str]]:
    """Worker: try Nominatim first; on failure, try Overpass; return (name, lat, lon, source)."""
    try:
        _, rate_geocode = _nominatim_geocoder()
        coords = geocode_via_nominatim(name, rate_geocode)
        if coords:
            lat, lon = coords
            with _print_lock:
                print(
                    f"[{i}/{total}] ✅ {name} -> ({lat:.5f}, {lon:.5f}) via Nominatim",
                    flush=True,
                )
            return (name, lat, lon, "nominatim")

        coords = geocode_via_overpass(name)
        if coords:
            lat, lon = coords
            with _print_lock:
                print(
                    f"[{i}/{total}] ✅ {name} -> ({lat:.5f}, {lon:.5f}) via Overpass",
                    flush=True,
                )
            return (name, lat, lon, "overpass")

        with _print_lock:
            print(f"[{i}/{total}] ⚠️  Could not geocode {name}", flush=True)
        return None
    except Exception as e:
        with _print_lock:
            print(f"[{i}/{total}] ❌ {name} failed with error: {e}", flush=True)
        return None


def build_or_update_coords(
    source: str = "auto", limit: Optional[int] = None
) -> pd.DataFrame:
    """
    Ensure munro_coords is populated for all (or `limit`) names from your Munro descriptions.
    Uses polite parallelisation and prints per-item progress with coordinates.
    """
    names = load_munro_names(source)
    if limit:
        names = names[:limit]

    conn = _ensure_conn()
    _ensure_schema(conn)

    existing = pd.read_sql_query("SELECT name FROM munro_coords", conn)["name"].tolist()
    missing = [n for n in names if n not in existing]

    if missing:
        total = len(missing)
        with _print_lock:
            print(
                f"[⋯] Geocoding {total} missing Munros (workers={MAX_WORKERS}) ...",
                flush=True,
            )

        rows = []
        completed, ok = 0, 0
        with ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS)) as ex:
            futures = {
                ex.submit(_process_one, idx, total, n): n
                for idx, n in enumerate(missing, start=1)
            }
            for fut in as_completed(futures):
                completed += 1
                res = fut.result()
                if res:
                    name, lat, lon, src = res
                    rows.append((name, lat, lon, src, datetime.utcnow().isoformat()))
                    ok += 1

        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO munro_coords (name, lat, lon, source, updated_at) VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()

        with _print_lock:
            print(f"[✓] Done: {ok}/{total} resolved; {total - ok} failed.", flush=True)

    df = pd.read_sql_query("SELECT name, lat, lon FROM munro_coords", conn)
    conn.close()
    return df


# ------------------------- Distance queries -------------------------


def _haversine_np(lat1, lon1, lat2, lon2):
    """Vectorised haversine distance between two sets of coordinates."""
    R = 6371.0088
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def geocode_location(query: str) -> Tuple[float, float]:
    """Geocode an arbitrary location string and return latitude/longitude."""
    _, rate_geocode = _nominatim_geocoder()
    loc = rate_geocode(query, exactly_one=True)
    if not loc:
        raise ValueError(f"Could not geocode location: {query}")
    return float(loc.latitude), float(loc.longitude)


def nearest_munros_to_point(lat: float, lon: float, k: int = 20) -> pd.DataFrame:
    """Return the *k* nearest Munros to a coordinate using cached distances."""
    conn = _ensure_conn()
    df = pd.read_sql_query("SELECT name, lat, lon FROM munro_coords", conn)
    conn.close()
    if df.empty:
        raise RuntimeError("munro_coords is empty. Run build_or_update_coords() first.")
    distances = _haversine_np(lat, lon, df["lat"].to_numpy(), df["lon"].to_numpy())
    out = df.copy()
    out["distance_km"] = distances
    out.sort_values("distance_km", inplace=True)
    return out.head(k).reset_index(drop=True)


def nearest_munros_from_user_location(
    user_location_str: str, k: int = 20
) -> pd.DataFrame:
    """Geocode a user-supplied string then delegate to ``nearest_munros_to_point``."""
    ulat, ulon = geocode_location(user_location_str)
    return nearest_munros_to_point(ulat, ulon, k=k)


# ------------------------- CLI -------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build Munro coordinate DB & query nearest."
    )
    parser.add_argument("--source", choices=["auto", "json", "sqlite"], default="auto")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--nearest", type=str, default=None)
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--csv", type=str, default=None)
    args = parser.parse_args()

    if args.build:
        df_all = build_or_update_coords(source=args.source, limit=args.limit)
        print(f"[✓] munro_coords entries now: {len(df_all)}")

    if args.nearest:
        if not os.path.exists(DB_PATH):
            raise SystemExit("No db.sqlite found. Run with --build first.")
        df = nearest_munros_from_user_location(args.nearest, k=args.k)
        print(df.to_string(index=False))
        if args.csv:
            df.to_csv(args.csv, index=False)
            print(f"[✓] Saved: {args.csv}")
