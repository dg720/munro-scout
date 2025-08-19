from flask import Blueprint, request, jsonify
from extensions.llm import get_llm
from services.search_service import (
    search_core,
    compact_dataset_slice,
    format_compact_lines,
    pick_route_names_llm,
    names_to_ids,
)
from utils.query import normalize_grade_max

bp = Blueprint("chat", __name__)


@bp.post("/chat")
def chat():
    llm, use_llm = get_llm()
    if not use_llm:
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

    import json

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

    # 2) Retrieval via shared search logic
    search_payload = {
        "query": intent.get("query") or "",
        "include_tags": intent.get("include_tags") or [],
        "exclude_tags": intent.get("exclude_tags") or [],
        "bog_max": intent.get("bog_max"),
        "grade_max": normalize_grade_max(intent.get("grade_max")),
        "limit": limit,
    }
    search_resp = search_core(search_payload)
    candidates = search_resp["results"]

    def to_route_link(r):
        return {"id": r["id"], "name": r["name"], "tags": r.get("tags", [])}

    route_links = [to_route_link(r) for r in candidates[:limit]]

    # 3) Broad LLM fallback
    broad_used = False
    dataset_summary = ""
    if not candidates:
        data_slice = compact_dataset_slice(limit_items=250)
        dataset_summary = format_compact_lines(data_slice, cap=120)
        broad_used = True
        picked_names = pick_route_names_llm(dataset_summary, user_msg)
        mapped = names_to_ids(picked_names)
        if mapped:
            # get tags for mapped ids
            from db import get_db

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

    # 4) Build context for synthesis
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

    # 5) Synthesis
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
            "routes": route_links,
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
