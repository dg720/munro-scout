from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

print("🚀 Starting Munro Flask API...")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)

DB_PATH = "db.sqlite"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/munros")
def get_munros():
    grade = request.args.get("grade", type=int)
    bog = request.args.get("bog", type=int)
    search = request.args.get("search", type=str)

    # Build dynamic SQL (we'll keep filters that match your known schema)
    base_sql = "SELECT * FROM munros WHERE 1=1"
    clauses = []
    params = []

    if grade is not None:
        clauses.append("AND grade = ?")
        params.append(grade)

    if bog is not None:
        clauses.append("AND bog <= ?")
        params.append(bog)

    if search:
        # Case-insensitive LIKE on name/summary/description if present
        # These columns exist in your seed if present in JSON
        clauses.append("""
            AND (
                name LIKE ? COLLATE NOCASE
                OR summary LIKE ? COLLATE NOCASE
                OR description LIKE ? COLLATE NOCASE
            )
        """)
        like = f"%{search}%"
        params.extend([like, like, like])

    sql = " ".join([base_sql, *clauses])

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Convert to dict and drop internal fields
    out = []
    for r in rows:
        d = dict(r)
        d.pop("normalized_name", None)  # internal
        out.append(d)

    return jsonify(out), 200, {"Content-Type": "application/json; charset=utf-8"}


if __name__ == "__main__":
    app.run(debug=True)
