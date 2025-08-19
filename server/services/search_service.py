from typing import Any, Dict, List, Tuple
from db import get_db
from utils.query import (
    expand_query_for_fts,
    build_like_terms,
    normalize_grade_max,
    norm_text,
)
from extensions.llm import get_llm

# ---------- Core search (3-pass) ----------


def search_core(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload keys: query, include_tags, exclude_tags, bog_max, grade_max, limit
    Returns dict with sql/params/results and the expanded fts_query used.
    """
    raw_query = (payload.get("query") or "").strip()
    include_tags = payload.get("include_tags") or []
    exclude_tags = payload.get("exclude_tags") or []
    bog_max = payload.get("bog_max")
    grade_max = normalize_grade_max(payload.get("grade_max"))
    limit = int(payload.get("limit") or 12)

    with get_db() as conn:
        c = conn.cursor()

        rows = []
        used_sql, used_params = "", []
        fts_query = expand_query_for_fts(raw_query)

        # Pass 1: FTS (no bm25)
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

            if bog_max is not None:
                wheres.append("(m.bog IS NULL OR m.bog <= ?)")
                where_params.append(bog_max)
            if grade_max is not None:
                wheres.append("(m.grade IS NULL OR m.grade <= ?)")
                where_params.append(grade_max)

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

        # Pass 2: LIKE fallback
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

                block = "m.name LIKE ? COLLATE NOCASE OR m.summary LIKE ? COLLATE NOCASE OR m.description LIKE ? COLLATE NOCASE"
                blocks, like_params = [], []
                for term in like_terms:
                    blocks.append(f"({block})")
                    like_params.extend([term, term, term])
                wheres2.append("(" + " OR ".join(blocks) + ")")
                where_params2.extend(like_params)

                if bog_max is not None:
                    wheres2.append("(m.bog IS NULL OR m.bog <= ?)")
                    where_params2.append(bog_max)
                if grade_max is not None:
                    wheres2.append("(m.grade IS NULL OR m.grade <= ?)")
                    where_params2.append(grade_max)

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

        # Pass 3: Tag-only fallback
        if not rows and (include_tags):
            joins3 = ["JOIN munro_tags t_in ON t_in.munro_id = m.id"]
            wheres3, where_params3 = ["1=1"], []

            if bog_max is not None:
                wheres3.append("(m.bog IS NULL OR m.bog <= ?)")
                where_params3.append(bog_max)
            if grade_max is not None:
                wheres3.append("(m.grade IS NULL OR m.grade <= ?)")
                where_params3.append(grade_max)

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

        ids = [r["id"] for r in rows]
        tags_map = {}
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
    lines = []
    for item in data[:cap]:
        line = f"- {item['name']} | tags: {item['tags']} | terrain: {item['terrain']} | transport: {item['transport']} | start: {item['start']} | {item['summary']}"
        lines.append(line)
    return "\n".join(lines)


def pick_route_names_llm(dataset_lines: str, user_msg: str) -> list[str]:
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
