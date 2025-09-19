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
from utils.filters import parse_numeric_filters  # NEW

bp = Blueprint("chat", __name__)

# Heuristic location extractor with guard against "at least", numbers, units, etc.
_FILTER_STOP = r"(?:at\s+least|at\s+most|more\s+than|less\s+than|over|under|between|within|with|for|of|\d+|km|mi|miles|kilomet)"

_LOCATION_PATTERNS = [
    r"\bnear\s+([A-Za-z][A-Za-z\s'\-]+?)(?=\s+" + _FILTER_STOP + r"|\s*$|[.,;:!?])",
    r"\bclose\s+to\s+([A-Za-z][A-Za-z\s'\-]+?)(?=\s+"
    + _FILTER_STOP
    + r"|\s*$|[.,;:!?])",
    r"\baround\s+([A-Za-z][A-Za-z\s'\-]+?)(?=\s+" + _FILTER_STOP + r"|\s*$|[.,;:!?])",
    r"\bin\s+([A-Za-z][A-Za-z\s'\-]+?)(?=\s+" + _FILTER_STOP + r"|\s*$|[.,;:!?])",
    r"\bat\s+(?!least\b|most\b)([A-Za-z][A-Za-z\s'\-]+?)(?=\s+"
    + _FILTER_STOP
    + r"|\s*$|[.,;:!?])",
    r"\bfrom\s+([A-Za-z][A-Za-z\s'\-]+?)(?=\s+" + _FILTER_STOP + r"|\s*$|[.,;:!?])",
]


def extract_location_heuristic(text: str) -> str:
    """Fallback regex extractor for locations when the LLM misses them."""

    s = (text or "").strip()
    for pat in _LOCATION_PATTERNS:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            loc = m.group(1).strip()
            return re.sub(r"[.,;:!?]+$", "", loc).strip()
    return ""


def _coerce_float(x):
    """Safely cast arbitrary payload values to floats or return ``None``."""

    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@bp.post("/chat")
def chat():
    """Conversational endpoint backed by shared search logic and an LLM."""

    llm, use_llm = get_llm()
    if not use_llm:
        return jsonify({"error": "LLM not configured"}), 500

    data = request.get_json(force=True) or {}
    user_msg = (data.get("message") or "").strip()
    limit = int(data.get("limit") or 8)
    debug = bool(data.get("debug") or False)

    # 1) Parse intent (now includes location + numeric filters)
    intent_prompt = f"""
You are an intent parser for a Munro route assistant.

Extract:
- compact FTS 'query'
- 'include_tags' and 'exclude_tags'
- 'location' (single string or null)
- numeric filters if present:
  - distance_min_km, distance_max_km (route length)
  - time_min_h, time_max_h (estimated time)

Examples:
- "at least 15km" -> distance_min_km = 15
- "under 6 hours" -> time_max_h = 6
- "between 10 and 15km" -> distance_min_km = 10, distance_max_km = 15

Allowed tags:
['ridge','scramble','technical','steep','rocky','boggy','heather','scree','handson','knifeedge','airy','slab','gully',
 'easy','moderate','hard','serious','pathless','loose_rock','cornice','river_crossing','slippery','exposure',
 'bus','train','bike','classic','views','waterfalls','bothy','scrambling','camping','multiday','popular','quiet','family']

Rules:
- Include only tags clearly implied. Be conservative.
- 'river_crossing' only if explicit wade/ford, not if a bridge/stepping stones exist.
- Return STRICT JSON keys: query, include_tags, exclude_tags, bog_max, grade_max, location,
  distance_min_km, distance_max_km, time_min_h, time_max_h.

User message: {user_msg}
"""
    try:
        intent_raw = llm.invoke(
            [
                {
                    "role": "system",
                    "content": "Extract structured filters for Munro search.",
                },
                {"role": "user", "content": intent_prompt},
            ]
        ).content.strip()
    except Exception:
        current_app.logger.exception("[chat] intent parsing failed; using fallback filters")
        intent_raw = ""

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
            "distance_min_km": None,
            "distance_max_km": None,
            "time_min_h": None,
            "time_max_h": None,
        }

    # Ensure keys exist
    for k in ("distance_min_km", "distance_max_km", "time_min_h", "time_max_h"):
        intent[k] = intent.get(k, None)

    # Heuristic fallbacks if the LLM missed key pieces of information.
    loc_heur = extract_location_heuristic(user_msg)
    if not (intent.get("location") or "").strip() and loc_heur:
        intent["location"] = loc_heur

    # Regex fallback for numeric filters
    num_fallback = parse_numeric_filters(user_msg)
    for k, v in num_fallback.items():
        if intent.get(k) is None:
            intent[k] = v

    # Coerce numeric strings to floats (if any)
    for k in ("distance_min_km", "distance_max_km", "time_min_h", "time_max_h"):
        intent[k] = _coerce_float(intent.get(k))

    # Log final intent for observability and debugging.
    current_app.logger.info(f"[chat] intent={intent} | limit={limit}")

    # 2) Retrieval via shared search logic
    location = (intent.get("location") or "").strip()

    if location:
        # Location-first path: distance-ranked, tags as soft boost
        try:
            search_resp = search_by_location_core(
                location=location,
                include_tags=intent.get("include_tags") or [],
                limit=limit,
                distance_min_km=intent.get("distance_min_km"),
                distance_max_km=intent.get("distance_max_km"),
                time_min_h=intent.get("time_min_h"),
                time_max_h=intent.get("time_max_h"),
            )
        except ValueError as e:
            # Location not in Scotland / not recognised
            return jsonify(
                {
                    "error": str(e),
                    "steps": {
                        "intent": intent,
                        "location": location,
                        "retrieval_mode": "location",
                    },
                }
            ), 400

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
            # pass numeric filters through to search_core
            "distance_min_km": intent.get("distance_min_km"),
            "distance_max_km": intent.get("distance_max_km"),
            "time_min_h": intent.get("time_min_h"),
            "time_max_h": intent.get("time_max_h"),
        }
        search_resp = search_core(search_payload)
        candidates = search_resp["results"]
        current_app.logger.info(
            f"[chat][fts-mode] q='{search_payload['query']}' -> {len(candidates)} candidates"
        )

    def to_route_link(r):
        """Compact representation for the UI route list."""

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
    try:
        answer = llm.invoke(
            [
                {
                    "role": "system",
                    "content": "Answer based only on the provided context.",
                },
                {"role": "user", "content": answer_prompt},
            ]
        ).content.strip()
    except Exception:
        current_app.logger.exception("[chat] answer synthesis failed; falling back to templated reply")
        if candidates:
            bullet_lines = []
            for r in candidates[:limit]:
                base = r.get("name", "Unknown route")
                tag_str = ", ".join(r.get("tags", []))
                if tag_str:
                    base += f" ({tag_str})"
                distance = r.get("route_distance") or r.get("distance_km")
                if isinstance(distance, (int, float)):
                    base += f", ~{float(distance):.1f} km"
                time_val = r.get("route_time")
                if isinstance(time_val, (int, float)):
                    base += f", ~{float(time_val):.1f} h"
                summary = (r.get("summary") or r.get("snippet") or "").strip()
                if summary:
                    base += f" – {summary[:140]}"
                bullet_lines.append(f"• {base}")
            answer = (
                "Here are some routes that match your filters:\n" + "\n".join(bullet_lines)
            )
        elif route_links:
            names = ", ".join(r.get("name", "Unknown route") for r in route_links)
            answer = (
                "I couldn't summarise the details just now, but these routes look relevant: "
                + names
            )
        else:
            answer = (
                "I couldn't reach the assistant to compose a reply, but I didn't find any "
                "matching routes either. Please try adjusting your request."
            )

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
                    "route_distance": r.get(
                        "route_distance"
                    ),  # present in location path after service update
                    "route_time": r.get("route_time"),
                }
                for r in candidates
            ],
        }

    return jsonify(
        {
            "answer": answer,
            "routes": route_links,  # for Details tab links/buttons
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
