import re
import json
from flask import Blueprint, request, jsonify, current_app
from extensions.llm import get_llm
from services.search_service import (
    search_core,
    search_by_location_core,
    compact_dataset_slice,
    format_compact_lines,
    pick_route_names_llm,
    names_to_ids,
)
from utils.query import normalize_grade_max

bp = Blueprint("chat", __name__)

# --- simple heuristic fallback for location phrases if LLM misses it ---
_LOCATION_PATTERNS = [
    r"\bnear\s+([A-Za-z][A-Za-z\s'\-]+)",
    r"\bclose\s+to\s+([A-Za-z][A-Za-z\s'\-]+)",
    r"\baround\s+([A-Za-z][A-Za-z\s'\-]+)",
    r"\bfrom\s+([A-Za-z][A-Za-z\s'\-]+)",
    r"\b(?:in|at)\s+([A-Za-z][A-Za-z\s'\-]+)",  # careful with generic 'in'
]


def extract_location_heuristic(text: str) -> str:
    s = (text or "").strip()
    for pat in _LOCATION_PATTERNS:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            loc = m.group(1).strip()
            # drop trailing punctuation
            loc = re.sub(r"[.,;:!?]+$", "", loc).strip()
            return loc
    return ""


@bp.post("/chat")
def chat():
    llm, use_llm = get_llm()
    if not use_llm:
        return jsonify({"error": "LLM not configured"}), 500

    data = request.get_json(force=True) or {}
    user_msg = (data.get("message") or "").strip()
    limit = int(data.get("limit") or 8)
    debug = bool(data.get("debug") or False)

    # 1) Parse intent (now includes 'location')
    intent_prompt = f"""
You are an intent parser for a Munro route assistant.

Extract a compact FTS query and tag filters from the user message, and detect a single free-text 'location' if the user mentions a place to start from or be near (e.g., "near Fort William", "from Glasgow", "close to Aviemore"). If no location is present, set it to null.

Allowed tags:
['ridge','scramble','technical','steep','rocky','boggy','heather','scree','handson','knifeedge','airy','slab','gully',
 'easy','moderate','hard','serious','pathless','loose_rock','cornice','river_crossing','slippery','exposure',
 'bus','train','bike','classic','views','waterfalls','bothy','scrambling','camping','multiday','popular','quiet','family']

Rules:
- Include only tags clearly implied. Be conservative.
- 'river_crossing' only if explicit wade/ford, not if a bridge/stepping stones exist.
- Transport: add 'bus'/'train' if feasible/mentioned; 'bike' if cycle access implied.
- If a place name or "near/from/around <place>" appears, set location to that place string.
- Return STRICT JSON with fields: query, include_tags, exclude_tags, bog_max, grade_max, location.

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
            "location": None,
        }

    # Fallback heuristics if LLM missed the location
    location = ""
    if isinstance(intent, dict) and intent.get("location") is not None:
        location = (intent.get("location") or "").strip()
    if not location:
        location = extract_location_heuristic(user_msg)

    current_app.logger.info(
        f"[chat] intent={intent} | fallback_location='{location}' | limit={limit}"
    )

    # 2) Retrieval via shared search logic
    if location:
        # Location-first path: distance-ranked, tags as soft boost
        search_resp = search_by_location_core(
            location=location,
            include_tags=intent.get("include_tags") or [],
            limit=limit,
        )
        candidates = search_resp["results"]

        # Server log: names + distances
        try:
            dist_list = [
                f"{r['name']} ({r.get('distance_km', 'na'):.1f} km)"
                if isinstance(r.get("distance_km"), (int, float))
                else f"{r['name']}"
                for r in candidates
            ]
        except Exception:
            dist_list = [r.get("name", "?") for r in candidates]
        current_app.logger.info(
            f"[chat][location-mode] '{location}' -> {len(candidates)} candidates: {', '.join(dist_list)}"
        )
    else:
        # Default text/tag search
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
        current_app.logger.info(
            f"[chat][fts-mode] q='{search_payload['query']}' -> {len(candidates)} candidates"
        )

    def to_route_link(r):
        return {"id": r["id"], "name": r["name"], "tags": r.get("tags", [])}

    route_links = [to_route_link(r) for r in candidates[:limit]]

    # 3) Broad LLM fallback if nothing retrieved
    broad_used = False
    dataset_summary = ""
    if not candidates:
        data_slice = compact_dataset_slice(limit_items=250)
        dataset_summary = format_compact_lines(data_slice, cap=120)
        broad_used = True
        picked_names = pick_route_names_llm(dataset_summary, user_msg)
        mapped = names_to_ids(picked_names)
        if mapped:
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

    # 4) Build context for synthesis (include distances if in location mode)
    is_location_mode = (search_resp.get("retrieval_mode") == "location") or bool(
        location
    )

    if candidates:
        ctx_chunks = []
        for r in candidates[:limit]:
            tag_str = ", ".join(r.get("tags", []))
            if is_location_mode:
                dist = r.get("distance_km")
                dist_txt = (
                    f" (~{dist:.1f} km)" if isinstance(dist, (int, float)) else ""
                )
                ctx_chunks.append(
                    f"- {r['name']}{dist_txt}: {tag_str}\n  {r['snippet']}"
                )
            else:
                ctx_chunks.append(f"- {r['name']}: {tag_str}\n  {r['snippet']}")
        context = "\n".join(ctx_chunks)
    else:
        context = f"""No exact matches from search. Consider these dataset items:

{dataset_summary}
"""

    # 5) Synthesis
    location_hint = (
        "Prioritise proximity and mention approximate distances. "
        if is_location_mode
        else ""
    )
    answer_prompt = f"""
You are a helpful Munro route assistant.
User asked: "{user_msg}"

Context:
{context}

Write a concise helpful answer:
- If exact matches were provided, start with 1–2 routes that best fit, then alternatives.
- If no exact matches were provided (dataset view), pick 3–6 routes that best fit and justify briefly.
- {location_hint}Explain why they fit (use tags like 'scramble','airy','bus','train','camping','multiday', etc.).
- Keep it under ~180 words and avoid generic filler.
"""
    answer = llm.invoke(
        [
            {"role": "system", "content": "Answer based only on the provided context."},
            {"role": "user", "content": answer_prompt},
        ]
    ).content.strip()

    # Retrieval mode string for debug
    retrieval_mode = (
        "location"
        if is_location_mode
        else ("fts/like/tag" if candidates else "llm_broad")
    )

    # Optional debug payload back to the client (behind flag)
    debug_block = None
    if debug:
        debug_block = {
            "location_mode": is_location_mode,
            "location": location or None,
            "intent": intent,
            "returned_munros": [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "distance_km": r.get("distance_km"),
                    "tags": r.get("tags", []),
                }
                for r in candidates
            ],
        }

    return jsonify(
        {
            "answer": answer,
            "routes": route_links,
            "steps": {
                "intent": intent,
                "retrieval_mode": retrieval_mode,
                "sql": search_resp.get("sql"),
                "params": search_resp.get("params"),
                "results": candidates,
                "broad_count": len(route_links) if broad_used else 0,
                "location": location or None,
                "debug": debug_block,
            },
        }
    )
