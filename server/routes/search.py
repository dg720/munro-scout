from flask import Blueprint, request, jsonify
from services.search_service import search_core

bp = Blueprint("search", __name__)


@bp.post("/search")
def search_munros():
    data = request.get_json(force=True) or {}
    # Normalize grade here to keep API parity
    resp = search_core(
        {
            "query": (data.get("query") or "").strip(),
            "include_tags": data.get("include_tags") or [],
            "exclude_tags": data.get("exclude_tags") or [],
            "bog_max": data.get("bog_max"),
            "grade_max": data.get("grade_max"),
            "limit": int(data.get("limit") or 12),
        }
    )
    return jsonify(resp)
