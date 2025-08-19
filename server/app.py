from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, os, json, re
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

    base_sql = "SELECT * FROM munros WHERE 1=1"
    clauses, params = [], []

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

SYNONYMS = {
    # geography / regions
    "skye": ["skye", "cuillin", "cuillins", "black cuillin", "red cuillin"],
    "cuillin": ["cuillin", "skye", "black cuillin", "red cuillin"],
    "glencoe": ["glencoe", "glen coe", "aonach eagach"],
    # activities / features
    "scramble": ["scramble", "scrambling"],
    "scrambles": ["scramble", "scrambling"],
    # transport hints
    "bus": ["bus", "buses"],
    "train": ["train", "rail", "railway", "station"],
    # feel / exposure
    "airy": ["airy", "exposed", "exposure"],
}


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"[^\w']+", (q or "").lower()) if t]


def expand_query_for_fts(q: str) -> str:
    """
    Turn 'scrambles isle of skye' into: 'scrambl* OR skye OR cuillin'
    (stopwords removed, synonyms expanded, simple prefixing for recall)
    """
    toks = _tokenize(q)
    terms: list[str] = []
    for t in toks:
        if t in STOPWORDS:
            continue
        for s in SYNONYMS.get(t, [t]):
            s = s.strip()
            if not s:
                continue
            if len(s) >= 5:
                terms.append(f"{s[:5]}*")  # crude stem/prefix
            else:
                terms.append(s)
    # dedupe while preserving order
    seen, uniq = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return " OR ".join(uniq) if uniq else ""


def build_like_terms(q: str) -> list[str]:
    toks = [t for t in _tokenize(q) if t not in STOPWORDS]
    expanded: list[str] = []
    for t in toks:
        expanded.extend(SYNONYMS.get(t, [t]))
    seen, out = set(), []
    for t in expanded:
        if t and t not in seen:
            seen.add(t)
            out.append(f"%{t}%")
    return out[:6]


# ---------- Search (FTS w/o bm25 + LIKE + tag-only) ----------
@app.route("/api/search", methods=["POST"])
def search_munros():
    """
    Body:
    {
      "query": "airy ridge near glencoe",
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
    grade_max = data.get("grade_max")
    limit = int(data.get("limit") or 12)

    with get_db() as conn:
        c = conn.cursor()

        rows = []
        used_sql, used_params = "", []
        fts_query = expand_query_for_fts(raw_query)

        # ---------- Pass 1: FTS (contentless table) — NO bm25 ----------
        if fts_query:
            wheres = ["1=1"]
            params: list = []

            joins = []
            having = ""
            if include_tags:
                joins.append("JOIN munro_tags t_in ON t_in.munro_id = m.id")
                wheres.append(f"t_in.tag IN ({','.join('?' for _ in include_tags)})")
                params.extend(include_tags)
                having = (
                    f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                    f"THEN t_in.tag END) = ?"
                )
                params.extend(include_tags)
                params.append(len(include_tags))

            exclude_sub = ""
            if exclude_tags:
                exclude_sub = f"""
                    AND m.id NOT IN (
                        SELECT munro_id FROM munro_tags
                        WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                    )
                """

            if bog_max is not None:
                wheres.append("(m.bog IS NULL OR m.bog <= ?)")
                params.append(bog_max)
            if grade_max is not None:
                wheres.append("(m.grade IS NULL OR m.grade <= ?)")
                params.append(grade_max)

            # Use a CTE to select matched docids; we won't compute scores.
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
                {exclude_sub}
                GROUP BY m.id
                {having}
                ORDER BY m.name ASC
                LIMIT ?
            """
            params_fts = [fts_query] + params + exclude_tags + [limit]
            rows = c.execute(sql_fts, params_fts).fetchall()
            used_sql, used_params = sql_fts, params_fts

        # ---------- Pass 2: LIKE fallback ----------
        if not rows and raw_query:
            like_terms = build_like_terms(raw_query)
            if like_terms:
                joins2, wheres2, params2 = [], ["1=1"], []

                having2 = ""
                if include_tags:
                    joins2.append("JOIN munro_tags t_in ON t_in.munro_id = m.id")
                    wheres2.append(
                        f"t_in.tag IN ({','.join('?' for _ in include_tags)})"
                    )
                    params2.extend(include_tags)
                    having2 = (
                        f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                        f"THEN t_in.tag END) = ?"
                    )
                    params2.extend(include_tags)
                    params2.append(len(include_tags))

                exclude_sub2 = ""
                if exclude_tags:
                    exclude_sub2 = f"""
                        AND m.id NOT IN (
                            SELECT munro_id FROM munro_tags
                            WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                        )
                    """

                block = "m.name LIKE ? COLLATE NOCASE OR m.summary LIKE ? COLLATE NOCASE OR m.description LIKE ? COLLATE NOCASE"
                blocks, like_params = [], []
                for term in like_terms:
                    blocks.append(f"({block})")
                    like_params.extend([term, term, term])
                wheres2.append("(" + " OR ".join(blocks) + ")")

                if bog_max is not None:
                    wheres2.append("(m.bog IS NULL OR m.bog <= ?)")
                    params2.append(bog_max)
                if grade_max is not None:
                    wheres2.append("(m.grade IS NULL OR m.grade <= ?)")
                    params2.append(grade_max)

                sql_like = f"""
                    SELECT m.id, m.name, m.summary, m.description,
                           1000.0 AS rank
                    FROM munros m
                    {" ".join(joins2) if joins2 else ""}
                    WHERE {" AND ".join(wheres2)}
                    {exclude_sub2}
                    GROUP BY m.id
                    {having2}
                    ORDER BY m.name ASC
                    LIMIT ?
                """
                params_like = params2 + like_params + exclude_tags + [limit]
                rows = c.execute(sql_like, params_like).fetchall()
                used_sql, used_params = sql_like, params_like

        # ---------- Pass 3: Tag-only fallback ----------
        if not rows and include_tags:
            joins3 = ["JOIN munro_tags t_in ON t_in.munro_id = m.id"]
            wheres3, params3 = ["1=1"], []
            having3 = (
                f"HAVING COUNT(DISTINCT CASE WHEN t_in.tag IN ({','.join('?' for _ in include_tags)}) "
                f"THEN t_in.tag END) = ?"
            )
            params3.extend(include_tags)
            params3.append(len(include_tags))

            exclude_sub3 = ""
            if exclude_tags:
                exclude_sub3 = f"""
                    AND m.id NOT IN (
                        SELECT munro_id FROM munro_tags
                        WHERE tag IN ({",".join("?" for _ in exclude_tags)})
                    )
                """

            if bog_max is not None:
                wheres3.append("(m.bog IS NULL OR m.bog <= ?)")
                params3.append(bog_max)
            if grade_max is not None:
                wheres3.append("(m.grade IS NULL OR m.grade <= ?)")
                params3.append(grade_max)

            sql_tags = f"""
                SELECT m.id, m.name, m.summary, m.description,
                       2000.0 AS rank
                FROM munros m
                {" ".join(joins3)}
                WHERE {" AND ".join(wheres3)}
                {exclude_sub3}
                GROUP BY m.id
                {having3}
                ORDER BY m.name ASC
                LIMIT ?
            """
            params_tags = params3 + exclude_tags + [limit]
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
        "grade_max": intent.get("grade_max"),
        "limit": limit,
    }
    with app.test_request_context("/api/search", method="POST", json=payload):
        resp = search_munros()
    search_resp = resp.get_json()

    candidates = search_resp["results"]

    # ---------- Broad LLM fallback over compact dataset if nothing found ----------
    broad_used = False
    dataset_summary = ""
    if not candidates:
        with get_db() as conn:
            # compact slice of the dataset (no full descriptions)
            rows = conn.execute("""
                SELECT m.id, m.name, m.summary, m.terrain, m.public_transport, m.start,
                       COALESCE(GROUP_CONCAT(t.tag, '|'), '') AS tags
                FROM munros m
                LEFT JOIN munro_tags t ON t.munro_id = m.id
                GROUP BY m.id
                ORDER BY m.name ASC
                LIMIT 200
            """).fetchall()
        # Format compact lines for the LLM
        lines = []
        for r in rows:
            tags = (r["tags"] or "").replace("|", ", ")
            summ = r["summary"] or ""
            if len(summ) > 220:
                summ = summ[:220] + "…"
            line = f"- {r['name']} | tags: {tags} | terrain: {r['terrain'] or ''} | transport: {r['public_transport'] or ''} | start: {r['start'] or ''} | {summ}"
            lines.append(line)
        dataset_summary = "\n".join(lines[:120])  # cap items to keep token-safe
        broad_used = True

    # 3) Build context for synthesis
    if candidates:
        ctx_chunks = []
        for r in candidates[:limit]:
            tag_str = ", ".join(r["tags"])
            ctx_chunks.append(f"- {r['name']}: {tag_str}\n  {r['snippet']}")
        context = "\n".join(ctx_chunks)
    else:
        # Provide the LLM a compact dataset to reason over
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
- If exact matches were provided, start with 1–2 routes that best fit the user's ask, then alternatives.
- If no exact matches were provided (dataset view), pick 3–6 routes that best fit and justify briefly.
- Explain why they fit (use tags like 'scramble','airy','bus','train','camping','multiday', etc.).
- Offer transport hints if 'bus'/'train' are present.
- If few fits, say that and suggest how to broaden the search.
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
            "steps": {
                "intent": intent,
                "retrieval_mode": ("fts/like/tag" if candidates else "llm_broad"),
                "retrieval_sql": search_resp["sql"],
                "retrieval_params": search_resp["params"],
                "candidates": candidates,
                "broad_count": dataset_summary.count("\n")
                + (1 if dataset_summary else 0),
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
