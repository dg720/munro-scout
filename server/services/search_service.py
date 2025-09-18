import logging
from typing import Any, Dict, List, Optional
from db import get_db
from utils.query import (
    expand_query_for_fts,
    build_like_terms,
    normalize_grade_max,
    norm_text,
)
from extensions.llm import get_llm
from services.geo_service import nearest_by_location, _map_names_to_db_rows, attach_tags

logger = logging.getLogger("search_service")

# --- Detect optional columns once (distance, time) ---
_HAS_DISTANCE: Optional[bool] = None
_HAS_TIME: Optional[bool] = None


def _ensure_schema_flags() -> None:
    """Detect once whether optional distance/time columns exist in the DB."""
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
        # Be conservative if we can't introspect
        _HAS_DISTANCE = False
        _HAS_TIME = False


def _add_numeric_filters(
    wheres: List[str],
    where_params: List[Any],
    dist_min: Optional[float],
    dist_max: Optional[float],
    time_min: Optional[float],
    time_max: Optional[float],
) -> None:
    """Append numeric filter SQL to WHERE (only if columns exist)."""
    _ensure_schema_flags()
    if _HAS_DISTANCE and dist_min is not None:
        wheres.append("(m.distance IS NULL OR m.distance >= ?)")
        where_params.append(float(dist_min))
    if _HAS_DISTANCE and dist_max is not None:
        wheres.append("(m.distance IS NULL OR m.distance <= ?)")
        where_params.append(float(dist_max))
    if _HAS_TIME and time_min is not None:
        wheres.append("(m.time IS NULL OR m.time >= ?)")
        where_params.append(float(time_min))
    if _HAS_TIME and time_max is not None:
        wheres.append("(m.time IS NULL OR m.time <= ?)")
        where_params.append(float(time_max))


# ---------- Core search (3-pass) ----------


def search_core(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the three-pass text search pipeline over the Munro dataset."""
    # payload keys: query, include_tags, exclude_tags, bog_max, grade_max, limit,
    #               distance_min_km, distance_max_km, time_min_h, time_max_h
    raw_query = (payload.get("query") or "").strip()
    include_tags = payload.get("include_tags") or []
    exclude_tags = payload.get("exclude_tags") or []
    bog_max = payload.get("bog_max")
    grade_max = normalize_grade_max(payload.get("grade_max"))
    limit = int(payload.get("limit") or 12)

    # New numeric filters
    dist_min = payload.get("distance_min_km")
    dist_max = payload.get("distance_max_km")
    time_min = payload.get("time_min_h")
    time_max = payload.get("time_max_h")

    with get_db() as conn:
        c = conn.cursor()

        rows = []
        used_sql, used_params = "", []
        fts_query = expand_query_for_fts(raw_query)

        # ---------- Pass 1: FTS (no bm25) ----------
        if fts_query:
            wheres, joins = ["1=1"], []
            where_params, having_clause, having_params = [], "", []

            if include_tags:
                joins.append("JOIN munro_tags t_in ON t_in.munro_id = m.id")
                wheres.append(f"t_in.tag IN ({','.join('?' for _ in include_tags)})")
                where_params.extend(include_tags)
                having_clause = (
                    f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                    f"THEN t_in.tag END) = ?"
                )
                having_params.extend(include_tags)
                having_params.append(len(include_tags))

            exclude_sql, exclude_params = "", []
            if exclude_tags:
                exclude_sql = f"""
                    AND m.id NOT IN (
                        SELECT munro_id FROM munro_tags
                        WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                    )
                """
                exclude_params = exclude_tags[:]

            # Numeric filters (WHERE)
            if bog_max is not None:
                wheres.append("(m.bog IS NULL OR m.bog <= ?)")
                where_params.append(bog_max)
            if grade_max is not None:
                wheres.append("(m.grade IS NULL OR m.grade <= ?)")
                where_params.append(grade_max)
            _add_numeric_filters(
                wheres, where_params, dist_min, dist_max, time_min, time_max
            )

            sql_fts = f"""
                WITH f AS (
                  SELECT rowid AS docid
                  FROM munro_fts
                  WHERE munro_fts MATCH ?
                )
                SELECT m.id, m.name, m.summary, m.description,
                       0.0 AS rank
                FROM f
                JOIN munros m ON m.id = f.docid
                {" ".join(joins) if joins else ""}
                WHERE {" AND ".join(wheres)}
                {exclude_sql}
                GROUP BY m.id
                {having_clause}
                ORDER BY m.name ASC
                LIMIT ?
            """
            params_fts = (
                [fts_query] + where_params + exclude_params + having_params + [limit]
            )
            rows = c.execute(sql_fts, params_fts).fetchall()
            used_sql, used_params = sql_fts, params_fts

        # ---------- Pass 2: LIKE fallback ----------
        if not rows and raw_query:
            like_terms = build_like_terms(raw_query)
            if like_terms:
                wheres2, joins2 = ["1=1"], []
                where_params2, having2, having_params2 = [], "", []

                if include_tags:
                    joins2.append("JOIN munro_tags t_in ON t_in.munro_id = m.id")
                    wheres2.append(
                        f"t_in.tag IN ({','.join('?' for _ in include_tags)})"
                    )
                    where_params2.extend(include_tags)
                    having2 = (
                        f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                        f"THEN t_in.tag END) = ?"
                    )
                    having_params2.extend(include_tags)
                    having_params2.append(len(include_tags))

                exclude_sql2, exclude_params2 = "", []
                if exclude_tags:
                    exclude_sql2 = f"""
                        AND m.id NOT IN (
                            SELECT munro_id FROM munro_tags
                            WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                        )
                    """
                    exclude_params2 = exclude_tags[:]

                # LIKE blocks
                block = "m.name LIKE ? COLLATE NOCASE OR m.summary LIKE ? COLLATE NOCASE OR m.description LIKE ? COLLATE NOCASE"
                blocks, like_params = [], []
                for term in like_terms:
                    blocks.append(f"({block})")
                    like_params.extend([term, term, term])
                wheres2.append("(" + " OR ".join(blocks) + ")")
                where_params2.extend(like_params)

                # Numeric filters (WHERE)
                if bog_max is not None:
                    wheres2.append("(m.bog IS NULL OR m.bog <= ?)")
                    where_params2.append(bog_max)
                if grade_max is not None:
                    wheres2.append("(m.grade IS NULL OR m.grade <= ?)")
                    where_params2.append(grade_max)
                _add_numeric_filters(
                    wheres2, where_params2, dist_min, dist_max, time_min, time_max
                )

                sql_like = f"""
                    SELECT m.id, m.name, m.summary, m.description,
                           1000.0 AS rank
                    FROM munros m
                    {" ".join(joins2) if joins2 else ""}
                    WHERE {" AND ".join(wheres2)}
                    {exclude_sql2}
                    GROUP BY m.id
                    {having2}
                    ORDER BY m.name ASC
                    LIMIT ?
                """
                params_like = where_params2 + exclude_params2 + having_params2 + [limit]
                rows = c.execute(sql_like, params_like).fetchall()
                used_sql, used_params = sql_like, params_like

        # ---------- Pass 3: Tag-only fallback ----------
        if not rows and include_tags:
            joins3 = ["JOIN munro_tags t_in ON t_in.munro_id = m.id"]
            wheres3, where_params3 = ["1=1"], []

            # Numeric filters (WHERE first)
            if bog_max is not None:
                wheres3.append("(m.bog IS NULL OR m.bog <= ?)")
                where_params3.append(bog_max)
            if grade_max is not None:
                wheres3.append("(m.grade IS NULL OR m.grade <= ?)")
                where_params3.append(grade_max)
            _add_numeric_filters(
                wheres3, where_params3, dist_min, dist_max, time_min, time_max
            )

            having3 = (
                f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                f"THEN t_in.tag END) = ?"
            )
            having_params3 = include_tags[:] + [len(include_tags)]

            exclude_sql3, exclude_params3 = "", []
            if exclude_tags:
                exclude_sql3 = f"""
                    AND m.id NOT IN (
                        SELECT munro_id FROM munro_tags
                        WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                    )
                """
                exclude_params3 = exclude_tags[:]

            sql_tags = f"""
                SELECT m.id, m.name, m.summary, m.description,
                       2000.0 AS rank
                FROM munros m
                {" ".join(joins3)}
                WHERE {" AND ".join(wheres3)}
                {exclude_sql3}
                GROUP BY m.id
                {having3}
                ORDER BY m.name ASC
                LIMIT ?
            """
            params_tags = where_params3 + exclude_params3 + having_params3 + [limit]
            rows = c.execute(sql_tags, params_tags).fetchall()
            used_sql, used_params = sql_tags, params_tags

        # ---------- Attach tags ----------
        ids = [r["id"] for r in rows]
        tags_map: Dict[int, List[str]] = {}
        if ids:
            tag_rows = c.execute(
                f"SELECT munro_id, tag FROM munro_tags WHERE munro_id IN ({','.join('?' for _ in ids)})",
                ids,
            ).fetchall()
            for tr in tag_rows:
                tags_map.setdefault(tr["munro_id"], []).append(tr["tag"])

        results = [
            {
                "id": r["id"],
                "name": r["name"],
                "summary": r["summary"],
                "snippet": (r["description"] or "")[:400],
                "tags": sorted(tags_map.get(r["id"], [])),
                "rank": r["rank"],
            }
            for r in rows
        ]

        return {
            "query": raw_query,
            "fts_query": fts_query,
            "include_tags": include_tags,
            "exclude_tags": exclude_tags,
            "bog_max": bog_max,
            "grade_max": grade_max,
            "sql": used_sql,
            "params": used_params,
            "results": results,
        }


# ---------- Compact dataset & LLM helpers ----------


def compact_dataset_slice(limit_items=200) -> list[dict]:
    """Return a trimmed dataset snapshot for broad LLM-based suggestions."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.name, m.summary, m.terrain, m.public_transport, m.start,
                   COALESCE(GROUP_CONCAT(t.tag, '|'), '') AS tags
            FROM munros m
            LEFT JOIN munro_tags t ON t.munro_id = m.id
            GROUP BY m.id
            ORDER BY m.name ASC
            LIMIT ?
        """,
            (limit_items,),
        ).fetchall()
    data = []
    for r in rows:
        tags = (r["tags"] or "").replace("|", ", ")
        summ = r["summary"] or ""
        if len(summ) > 220:
            summ = summ[:220] + "…"
        data.append(
            {
                "id": r["id"],
                "name": r["name"],
                "summary": summ,
                "terrain": r["terrain"] or "",
                "transport": r["public_transport"] or "",
                "start": r["start"] or "",
                "tags": tags,
            }
        )
    return data


def format_compact_lines(data: list[dict], cap=120) -> str:
    """Condense dataset rows into newline separated strings for prompts."""
    lines = []
    for item in data[:cap]:
        line = f"- {item['name']} | tags: {item['tags']} | terrain: {item['terrain']} | transport: {item['transport']} | start: {item['start']} | {item['summary']}"
        lines.append(line)
    return "\n".join(lines)


def pick_route_names_llm(dataset_lines: str, user_msg: str) -> list[str]:
    """Use the LLM to pick promising route names from a dataset summary."""
    llm, use_llm = get_llm()
    if not use_llm:
        return []
    prompt = f"""
From the dataset lines below, pick up to 6 route *names* that best match the user's request.

Rules:
- Only return names that appear verbatim in the dataset lines.
- Be conservative and prefer routes clearly matching the request (terrain/tags/transport/area).
- Return STRICT JSON: {{"names": ["Name One","Name Two"]}}

User request: "{user_msg}"

Dataset lines:
{dataset_lines}
"""
    raw = llm.invoke(
        [
            {
                "role": "system",
                "content": "Select matching items from a provided list and return strict JSON.",
            },
            {"role": "user", "content": prompt},
        ]
    ).content.strip()
    import json

    try:
        obj = json.loads(raw)
        names = obj.get("names") or []
        names = [n for n in names if isinstance(n, str) and n.strip()]
        return names[:6]
    except Exception:
        return []


def names_to_ids(names: list[str]) -> list[dict]:
    """Map human-readable route names back to database identifiers."""
    if not names:
        return []
    with get_db() as conn:
        all_rows = conn.execute("SELECT id, name FROM munros").fetchall()
        idx_exact = {r["name"]: r["id"] for r in all_rows}
        idx_loose = {norm_text(r["name"]): r["id"] for r in all_rows}

        out = []
        for n in names:
            if n in idx_exact:
                out.append({"id": idx_exact[n], "name": n})
                continue
            nid = idx_loose.get(norm_text(n))
            if nid:
                dbname = next(row["name"] for row in all_rows if row["id"] == nid)
                out.append({"id": nid, "name": dbname})
                continue
            row2 = conn.execute(
                "SELECT id, name FROM munros WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (f"%{n}%",),
            ).fetchone()
            if row2:
                out.append({"id": row2["id"], "name": row2["name"]})
        return out


# ---------- Location-first search (distance-weighted) ----------


def search_by_location_core(
    location: str,
    include_tags: Optional[List[str]],
    limit: int = 12,
    distance_min_km: Optional[float] = None,
    distance_max_km: Optional[float] = None,
    time_min_h: Optional[float] = None,
    time_max_h: Optional[float] = None,
) -> Dict[str, Any]:
    """Return Munros closest to a location, applying optional hard filters."""
    include_tags = include_tags or []

    # 1) Distance candidates (raises ValueError if location not in Scotland)
    near = nearest_by_location(location_query=location, k=max(20, limit))

    # 2) Map to DB rows & tags (rows contain: id, name, summary, description,
    #    distance_km [to user], and if available route_distance, route_time)
    rows = _map_names_to_db_rows(near)
    attach_tags(rows)

    # 3) HARD numeric filters on route attributes (if present)
    def _keep(r: Dict[str, Any]) -> bool:
        """Validate a candidate against the hard numeric constraints."""
        d = r.get("route_distance")  # km
        t = r.get("route_time")  # hours
        if (
            distance_min_km is not None
            and (d is not None)
            and d < float(distance_min_km)
        ):
            return False
        if (
            distance_max_km is not None
            and (d is not None)
            and d > float(distance_max_km)
        ):
            return False
        if time_min_h is not None and (t is not None) and t < float(time_min_h):
            return False
        if time_max_h is not None and (t is not None) and t > float(time_max_h):
            return False
        return True

    rows = [r for r in rows if _keep(r)]

    # 4) Soft re-ranking: distance first, then tag matches desc, then name
    def tag_match_count(tags: List[str]) -> int:
        """Return how many requested tags appear on the candidate."""
        return sum(1 for t in (tags or []) if t in include_tags)

    rows.sort(
        key=lambda r: (r["distance_km"], -tag_match_count(r.get("tags", [])), r["name"])
    )

    # 5) Build results (parity with search_core), include distance_km
    results = [
        {
            "id": r["id"],
            "name": r["name"],
            "summary": r.get("summary"),
            "snippet": (r.get("description") or "")[:400],
            "tags": r.get("tags", []),
            "rank": float(r["distance_km"]),  # smaller = better
            "distance_km": float(r["distance_km"]),
            "route_distance": r.get("route_distance"),
            "route_time": r.get("route_time"),
        }
        for r in rows[:limit]
    ]

    return {
        "query": "",
        "fts_query": "",
        "include_tags": include_tags,
        "exclude_tags": [],
        "bog_max": None,
        "grade_max": None,
        "sql": "[location-mode: distance rank]",
        "params": [location],
        "results": results,
        "location": location,
        "retrieval_mode": "location",
    }
