import sqlite3
from flask import current_app, g


def get_db():
    """Return a cached SQLite connection for the current Flask request."""
    if "db_conn" not in g:
        path = current_app.config["DB_PATH"]
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        # Store the connection on the Flask request context for reuse.
        g.db_conn = conn
    return g.db_conn


def close_db(e=None):
    """Close the request-scoped database connection if it exists."""
    conn = g.pop("db_conn", None)
    if conn is not None:
        # Connections are per-request, so close them on teardown.
        conn.close()


# Optional: register teardown in app factory if you prefer
def init_app(app):
    """Register teardown handling so the connection closes automatically."""
    app.teardown_appcontext(close_db)
