from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os, json, re, unicodedata
from dotenv import load_dotenv

# ---------- Boot ----------
print("🚀 Starting Munro Flask API...")
load_dotenv()

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)

DB_PATH = "db.sqlite"

# Optional LLM (used by /api/chat)
USE_LLM = True
try:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.getenv("MUNRO_CHAT_MODEL", "gpt-4o-mini"),  # or "gpt-3.5-turbo"
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
except Exception:
    USE_LLM = False
    llm = None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- Health ----------
@app.route("/api/health")
def health():
    return {"ok": True}


# ---------- Simple list with basic filters ----------
@app.route("/api/munros")
def get_munros():
    grade = request.args.get("grade", type=int)
    bog = request.args.get("bog", type=int)
    search = request.args.get("search", type=str)
    mid = request.args.get("id", type=int)  # optional id filter

    base_sql = "SELECT * FROM munros WHERE 1=1"
    clauses, params = [], []

    if mid is not None:
        clauses.append("AND id = ?")
        params.append(mid)

    if grade is not None:
        clauses.append("AND grade = ?")
        params.append(grade)

    if bog is not None:
        clauses.append("AND bog <= ?")
        params.append(bog)

    if search:
        clauses.append("""
            AND (
                name LIKE ? COLLATE NOCASE
                OR summary LIKE ? COLLATE NOCASE
                OR description LIKE ? COLLATE NOCASE
            )
        """)
        like = f"%{search}%"
        params.extend([like, like, like])

    sql = " ".join([base_sql, *clauses])

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d.pop("normalized_name", None)
        out.append(d)

    return jsonify(out), 200, {"Content-Type": "application/json; charset=utf-8"}


# ---------- Fetch one by id ----------
@app.route("/api/munro/<int:mid>")
def get_munro(mid):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM munros WHERE id = ?", (mid,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    d = dict(row)
    d.pop("normalized_name", None)
    return jsonify(d), 200


# ---------- Tag list (with counts) ----------
@app.route("/api/tags")
def list_tags():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT tag, COUNT(*) AS n
            FROM munro_tags
            GROUP BY tag
            ORDER BY n DESC, tag ASC
        """).fetchall()
    return jsonify([{"tag": r["tag"], "count": r["n"]} for r in rows])


# ---------- Query helpers (FTS expansion + LIKE fallback building) ----------
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "in",
    "on",
    "by",
    "for",
    "with",
    "at",
    "from",
    "near",
}

# Only tight, non-geo synonyms
GENERIC_SYNONYMS = {
    "scramble": ["scramble", "scrambling"],
    "scrambles": ["scramble", "scrambling"],
    "airy": ["airy", "exposed", "exposure"],
    "bus": ["bus", "buses"],
    "train": ["train", "rail", "railway", "station"],
}

DIFF_WORD_TO_NUM = {
    "easy": 3,
    "moderate": 4,
    "hard": 5,
    "serious": 5,
}


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"[^\w']+", (q or "").lower()) if t]


def _quote_or_prefix(term: str) -> str:
    """
    For FTS:
      - quote multi-word terms if present in the user query
      - prefix wildcard for long single words (len>=5)
      - keep short terms as-is
    """
    if " " in term:
        return f'"{term}"'
    return f"{term[:5]}*" if len(term) >= 5 else term


def expand_query_for_fts(q: str) -> str:
    """
    Location-agnostic expansion:
      - Remove stopwords
      - Expand only tight, non-geo synonyms (scramble/airy/bus/train)
      - No geo aliasing; rely purely on user tokens/phrases
    """
    toks = _tokenize(q)
    candidates: list[str] = []

    for t in toks:
        if t in STOPWORDS:
            continue
        candidates.extend(GENERIC_SYNONYMS.get(t, [t]))

    # dedupe, preserve order
    seen, cleaned = set(), []
    for s in candidates:
        s = s.strip()
        if not s:
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(s)

    terms = [_quote_or_prefix(s) for s in cleaned]
    return " OR ".join(terms) if terms else ""


def build_like_terms(q: str) -> list[str]:
    """LIKE fallback: conservative expansion (no geo aliasing), returns %term% patterns."""
    toks = _tokenize(q)
    expanded: list[str] = []
    for t in toks:
        if t in STOPWORDS:
            continue
        expanded.extend(GENERIC_SYNONYMS.get(t, [t]))

    seen, out = set(), []
    for t in expanded:
        t = t.strip()
        if not t:
            continue
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(f"%{t}%")
    return out[:12]


def normalize_grade_max(value):
    """Map grade_max to numeric with floor at 3 (3=easy, 4=moderate, 5=hard, 6=serious)."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        # accept strings "3", "4" etc, or words
        if v.isdigit():
            n = int(v)
            return n if n >= 3 else 3
        return DIFF_WORD_TO_NUM.get(v)
    # numeric
    try:
        n = int(value)
        return n if n >= 3 else 3
    except Exception:
        return None


# ---------- Search (FTS w/o bm25 + LIKE + tag-only) ----------
@app.route("/api/search", methods=["POST"])
def search_munros():
    """
    Body:
    {
      "query": "airy scramble by bus",
      "include_tags": ["scramble","exposure","bus"],
      "exclude_tags": ["boggy"],
      "bog_max": 3,
      "grade_max": 3,
      "limit": 12
    }
    """
    data = request.get_json(force=True) or {}
    raw_query = (data.get("query") or "").strip()
    include_tags = data.get("include_tags") or []
    exclude_tags = data.get("exclude_tags") or []
    bog_max = data.get("bog_max")
    grade_max_raw = data.get("grade_max")
    grade_max = normalize_grade_max(grade_max_raw)
    limit = int(data.get("limit") or 12)

    with get_db() as conn:
        c = conn.cursor()

        rows = []
        used_sql, used_params = "", []
        fts_query = expand_query_for_fts(raw_query)

        # ---------- Pass 1: FTS (contentless table) — NO bm25 ----------
        if fts_query:
            wheres = ["1=1"]
            joins = []
            where_params, having_clause, having_params = [], "", []

            # Include tags in WHERE (optional) AND in HAVING for AND-semantics
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

            exclude_sql = ""
            exclude_params = []
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
                wheres2 = ["1=1"]
                joins2 = []
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

                exclude_sql2 = ""
                exclude_params2 = []
                if exclude_tags:
                    exclude_sql2 = f"""
                        AND m.id NOT IN (
                            SELECT munro_id FROM munro_tags
                            WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                        )
                    """
                    exclude_params2 = exclude_tags[:]

                # Add LIKE blocks (in WHERE before numeric filters)
                block = "m.name LIKE ? COLLATE NOCASE OR m.summary LIKE ? COLLATE NOCASE OR m.description LIKE ? COLLATE NOCASE"
                blocks, like_params = [], []
                for term in like_terms:
                    blocks.append(f"({block})")
                    like_params.extend([term, term, term])
                wheres2.append("(" + " OR ".join(blocks) + ")")
                where_params2.extend(like_params)

                # Numeric filters (WHERE) after LIKEs
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

        # ---------- Pass 3: Tag-only fallback (AND semantics) ----------
        if not rows and include_tags:
            joins3 = ["JOIN munro_tags t_in ON t_in.munro_id = m.id"]
            wheres3 = ["1=1"]
            where_params3 = []

            # Numeric filters first (WHERE)
            if bog_max is not None:
                wheres3.append("(m.bog IS NULL OR m.bog <= ?)")
                where_params3.append(bog_max)
            if grade_max is not None:
                wheres3.append("(m.grade IS NULL OR m.grade <= ?)")
                where_params3.append(grade_max)

            # HAVING for AND-semantics on include tags
            having3 = (
                f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                f"THEN t_in.tag END) = ?"
            )
            having_params3 = include_tags[:] + [len(include_tags)]

            exclude_sql3 = ""
            exclude_params3 = []
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
        tags_map = {}
        if ids:
            tag_rows = c.execute(
                f"SELECT munro_id, tag FROM munro_tags WHERE munro_id IN ({','.join('?' for _ in ids)})",
                ids,
            ).fetchall()
            for tr in tag_rows:
                tags_map.setdefault(tr["munro_id"], []).append(tr["tag"])

        out = [
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

        return jsonify(
            {
                "query": raw_query,
                "fts_query": fts_query,
                "include_tags": include_tags,
                "exclude_tags": exclude_tags,
                "bog_max": bog_max,
                "grade_max": grade_max,
                "sql": used_sql,
                "params": used_params,
                "results": out,
            }
        )


# ---------- Helper: compact dataset slice for broad LLM fallback ----------
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


def _norm_text(s: str) -> str:
    """Lowercase, normalize apostrophes/diacritics for loose matching."""
    if not s:
        return ""
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()


def pick_route_names_llm(context: str, user_msg: str) -> list[str]:
    """Ask LLM to pick up to 6 route names from the provided context lines. Return list of names."""
    if not USE_LLM:
        return []
    prompt = f"""
From the dataset lines below, pick up to 6 route *names* that best match the user's request.

Rules:
- Only return names that appear verbatim in the dataset lines.
- Be conservative and prefer routes clearly matching the request (terrain/tags/transport/area).
- Return STRICT JSON: {{"names": ["Name One","Name Two"]}}

User request: "{user_msg}"

Dataset lines:
{context}
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
    try:
        obj = json.loads(raw)
        names = obj.get("names") or []
        names = [n for n in names if isinstance(n, str) and n.strip()]
        return names[:6]
    except Exception:
        return []


def names_to_ids(names: list[str]) -> list[dict]:
    """Map route names to (id,name); tolerate apostrophes/diacritics differences."""
    if not names:
        return []
    with get_db() as conn:
        # Preload name index for robust matching
        all_rows = conn.execute("SELECT id, name FROM munros").fetchall()
        idx_exact = {r["name"]: r["id"] for r in all_rows}
        idx_loose = {_norm_text(r["name"]): r["id"] for r in all_rows}

        out = []
        for n in names:
            # 1) exact
            if n in idx_exact:
                out.append({"id": idx_exact[n], "name": n})
                continue
            # 2) loose normalized
            nid = idx_loose.get(_norm_text(n))
            if nid:
                # use canonical DB name
                dbname = next(row["name"] for row in all_rows if row["id"] == nid)
                out.append({"id": nid, "name": dbname})
                continue
            # 3) fallback LIKE
            row2 = conn.execute(
                "SELECT id, name FROM munros WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (f"%{n}%",),
            ).fetchone()
            if row2:
                out.append({"id": row2["id"], "name": row2["name"]})
        return out


# ---------- Chat endpoint (RAG) ----------
@app.route("/api/chat", methods=["POST"])
def chat():
    if not USE_LLM:
        return jsonify({"error": "LLM not configured"}), 500

    data = request.get_json(force=True) or {}
    user_msg = (data.get("message") or "").strip()
    limit = int(data.get("limit") or 8)

    # 1) Parse intent
    intent_prompt = f"""
You are an intent parser for a Munro route assistant.
Extract a compact FTS query and tag filters from the user message. Use only these tags:
['ridge','scramble','technical','steep','rocky','boggy','heather','scree','handson','knifeedge','airy','slab','gully',
 'easy','moderate','hard','serious','pathless','loose_rock','cornice','river_crossing','slippery','exposure',
 'bus','train','bike','classic','views','waterfalls','bothy','scrambling','camping','multiday','popular','quiet','family']

Rules:
- Include only tags clearly implied. Be conservative.
- 'river_crossing' only if explicit wade/ford, no bridge/stepping stones.
- Transport: add 'bus'/'train' if feasible/mentioned; 'bike' if cycle access implied.
- Return STRICT JSON with fields: query, include_tags, exclude_tags, bog_max, grade_max.

User message: {user_msg}
"""
    intent_raw = llm.invoke(
        [
            {
                "role": "system",
                "content": "Extract structured filters for Munro search.",
            },
            {"role": "user", "content": intent_prompt},
        ]
    ).content.strip()

    try:
        intent = json.loads(intent_raw)
    except Exception:
        intent = {
            "query": user_msg,
            "include_tags": [],
            "exclude_tags": [],
            "bog_max": None,
            "grade_max": None,
        }

    # 2) Retrieval via the search logic
    payload = {
        "query": intent.get("query") or "",
        "include_tags": intent.get("include_tags") or [],
        "exclude_tags": intent.get("exclude_tags") or [],
        "bog_max": intent.get("bog_max"),
        "grade_max": normalize_grade_max(intent.get("grade_max")),  # normalize here too
        "limit": limit,
    }
    with app.test_request_context("/api/search", method="POST", json=payload):
        resp = search_munros()
    search_resp = resp.get_json()
    candidates = search_resp["results"]

    # Build link metadata for UI
    def to_route_link(r):
        return {"id": r["id"], "name": r["name"], "tags": r.get("tags", [])}

    route_links = [to_route_link(r) for r in candidates[:limit]]

    # ---------- Broad LLM fallback over compact dataset if nothing found ----------
    broad_used = False
    dataset_summary = ""
    if not candidates:
        data_slice = compact_dataset_slice(limit_items=250)
        dataset_summary = format_compact_lines(data_slice, cap=120)
        broad_used = True

        # Ask LLM to pick names and map them to IDs
        picked_names = pick_route_names_llm(dataset_summary, user_msg)
        mapped = names_to_ids(picked_names)
        if mapped:
            with get_db() as conn:
                ids = [m["id"] for m in mapped]
                tag_rows = conn.execute(
                    f"SELECT munro_id, tag FROM munro_tags WHERE munro_id IN ({','.join('?' for _ in ids)})",
                    ids,
                ).fetchall()
            tmap = {}
            for tr in tag_rows:
                tmap.setdefault(tr["munro_id"], []).append(tr["tag"])
            route_links = [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "tags": sorted(tmap.get(m["id"], [])),
                }
                for m in mapped
            ]

    # 3) Build context for synthesis
    if candidates:
        ctx_chunks = []
        for r in candidates[:limit]:
            tag_str = ", ".join(r.get("tags", []))
            ctx_chunks.append(f"- {r['name']}: {tag_str}\n  {r['snippet']}")
        context = "\n".join(ctx_chunks)
    else:
        context = f"""No exact matches from search. Consider these dataset items:

{dataset_summary}
"""

    # 4) Synthesis
    answer_prompt = f"""
You are a helpful Munro route assistant.
User asked: "{user_msg}"

Context:
{context}

Write a concise helpful answer:
- If exact matches were provided, start with 1–2 routes that best fit, then alternatives.
- If no exact matches were provided (dataset view), pick 3–6 routes that best fit and justify briefly.
- Explain why they fit (use tags like 'scramble','airy','bus','train','camping','multiday', etc.).
- Offer transport hints if 'bus'/'train' are present.
- Keep it under ~180 words and avoid generic filler.
"""
    answer = llm.invoke(
        [
            {"role": "system", "content": "Answer based only on the provided context."},
            {"role": "user", "content": answer_prompt},
        ]
    ).content.strip()

    return jsonify(
        {
            "answer": answer,
            "routes": route_links,  # buttons/hyperlinks for Details tab
            "steps": {
                "intent": intent,
                "retrieval_mode": ("fts/like/tag" if candidates else "llm_broad"),
                "sql": search_resp.get("sql"),
                "params": search_resp.get("params"),
                "results": candidates,
                "broad_count": len(route_links) if broad_used else 0,
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
