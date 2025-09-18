import sqlite3
from flask import current_app, g


def get_db():
    """Return a request-scoped SQLite connection with row factory configured."""

    if "db_conn" not in g:
        path = current_app.config["DB_PATH"]
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn


def close_db(e=None):
    """Close the request-scoped database connection if it was opened."""

    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


# Optional: register teardown in app factory if you prefer
def init_app(app):
    """Attach the database teardown handler to the Flask application."""

    app.teardown_appcontext(close_db)
