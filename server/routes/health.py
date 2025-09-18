from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Return a simple health indicator for monitoring probes."""
    return jsonify({"ok": True})
