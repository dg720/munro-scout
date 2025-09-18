from flask import Blueprint, jsonify
from services.munro_service import list_tags_with_counts

bp = Blueprint("tags", __name__)


@bp.get("/tags")
def list_tags():
    """List all route tags with usage counts for filter UIs."""

    return jsonify(list_tags_with_counts())
