from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

print("🚀 Starting Munro Flask API...")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # keep Unicode characters as-is
CORS(app)  # enable all origins for demo

DB_PATH = "db.sqlite"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict-like rows
    return conn


@app.route("/api/munros")
def get_munros():
    # Parse filters
    grade = request.args.get("grade", type=int)
    bog = request.args.get("bog", type=int)
    search = request.args.get("search", type=str)

    # Build query with explicit column list (avoid SELECT *)
    base_sql = """
        SELECT
            id,
            name,
            summary,
            distance,
            time,
            grade,
            bog,
            start,
            gpx_file
        FROM munros
        WHERE 1=1
    """
    clauses = []
    params = []

    if grade is not None:
        clauses.append("AND grade = ?")
        params.append(grade)

    if bog is not None:
        clauses.append("AND bog <= ?")
        params.append(bog)

    if search:
        # Simple case-insensitive search over name/summary
        clauses.append(
            "AND (name LIKE ? COLLATE NOCASE OR summary LIKE ? COLLATE NOCASE)"
        )
        like = f"%{search}%"
        params.extend([like, like])

    sql = " ".join([base_sql, *clauses])

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Convert rows to plain dicts
    results = [dict(r) for r in rows]

    return jsonify(results), 200, {"Content-Type": "application/json; charset=utf-8"}


if __name__ == "__main__":
    app.run(debug=True)
