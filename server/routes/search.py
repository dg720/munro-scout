from flask import Blueprint, request, jsonify
from services.search_service import search_core, search_by_location_core

bp = Blueprint("search", __name__)


@bp.post("/search")
def search_munros():
    """Dispatch searches via either text/tag filters or location lookups."""
    data = request.get_json(force=True) or {}
    location = (data.get("location") or "").strip()
    limit = int(data.get("limit") or 12)

    if location:
        # Location-first path: softer semantics, distance-weighted
        include_tags = data.get("include_tags") or []
        # Let the service layer handle distance-weighted results.
        resp = search_by_location_core(
            location=location, include_tags=include_tags, limit=limit
        )
        return jsonify(resp)

    # Default text/tag search path
    # Build the payload once so the service can execute the multi-pass strategy.
    resp = search_core(
        {
            "query": (data.get("query") or "").strip(),
            "include_tags": data.get("include_tags") or [],
            "exclude_tags": data.get("exclude_tags") or [],
            "bog_max": data.get("bog_max"),
            "grade_max": data.get("grade_max"),
            "limit": limit,
        }
    )
    return jsonify(resp)
