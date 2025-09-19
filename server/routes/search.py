from flask import Blueprint, request, jsonify
from services.search_service import search_core, search_by_location_core

bp = Blueprint("search", __name__)


@bp.post("/search")
def search_munros():
    """Execute a search request using either location or text filters.

    Request JSON keys:
    - ``location`` (str, optional): place name to anchor a nearest-hill lookup.
    - ``query`` (str, optional): free-text search terms.
    - ``include_tags``/``exclude_tags`` (list[str], optional): tag filters.
    - ``bog_max``/``grade_max`` (int, optional): upper bounds for bog/grade.
    - ``distance_min_km``/``distance_max_km`` (float, optional): route length
      filters in kilometres.
    - ``time_min_h``/``time_max_h`` (float, optional): estimated time filters
      in hours.
    - ``limit`` (int, optional): maximum number of results (default 12).

    Returns JSON mirroring :func:`search_core` or :func:`search_by_location_core`.
    """

    data = request.get_json(force=True) or {}
    location = (data.get("location") or "").strip()
    limit = int(data.get("limit") or 12)

    def _coerce_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    distance_min_km = _coerce_float(data.get("distance_min_km"))
    distance_max_km = _coerce_float(data.get("distance_max_km"))
    time_min_h = _coerce_float(data.get("time_min_h"))
    time_max_h = _coerce_float(data.get("time_max_h"))

    if location:
        # Location-first path: softer semantics, distance-weighted
        include_tags = data.get("include_tags") or []
        resp = search_by_location_core(
            location=location,
            include_tags=include_tags,
            limit=limit,
            distance_min_km=distance_min_km,
            distance_max_km=distance_max_km,
            time_min_h=time_min_h,
            time_max_h=time_max_h,
        )
        return jsonify(resp)

    # Default text/tag search path
    resp = search_core(
        {
            "query": (data.get("query") or "").strip(),
            "include_tags": data.get("include_tags") or [],
            "exclude_tags": data.get("exclude_tags") or [],
            "bog_max": data.get("bog_max"),
            "grade_max": data.get("grade_max"),
            "limit": limit,
            "distance_min_km": distance_min_km,
            "distance_max_km": distance_max_km,
            "time_min_h": time_min_h,
            "time_max_h": time_max_h,
        }
    )
    return jsonify(resp)
