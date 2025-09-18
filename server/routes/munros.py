from flask import Blueprint, request, jsonify
from services.munro_service import list_munros, get_munro as fetch_one

bp = Blueprint("munros", __name__)


@bp.get("/munros")
def get_munros():
    """Return a filtered list of Munros based on optional query parameters."""

    # Extract primitive filters directly from query parameters.
    grade = request.args.get("grade", type=int)
    bog = request.args.get("bog", type=int)
    search = request.args.get("search", type=str)
    mid = request.args.get("id", type=int)

    # Delegate to the service layer so filtering logic is centralised.
    out = list_munros(grade=grade, bog=bog, search=search, mid=mid)
    return jsonify(out), 200, {"Content-Type": "application/json; charset=utf-8"}


@bp.get("/munro/<int:mid>")
def get_munro(mid: int):
    """Return a single Munro entry by numeric identifier."""

    d = fetch_one(mid)
    if not d:
        return jsonify({"error": "not found"}), 404
    return jsonify(d), 200
