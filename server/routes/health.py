from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Health-check endpoint used by hosting providers."""

    return jsonify({"ok": True})
