from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

print("🚀 Starting Munro Flask API...")

app = Flask(__name__)
CORS(app)  # enable all origins for demo

DB_PATH = "db.sqlite"


@app.route("/api/munros")
def get_munros():
    grade = request.args.get("grade")
    bog = request.args.get("bog")
    search = request.args.get("search")

    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = lambda b: b.decode(errors="ignore")  # ensure UTF-8 decoding
    c = conn.cursor()

    query = "SELECT * FROM munros WHERE 1=1"
    params = []

    if grade:
        query += " AND grade = ?"
        params.append(grade)
    if bog:
        query += " AND bog <= ?"
        params.append(bog)
    if search:
        query += " AND (name LIKE ? OR summary LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    rows = c.execute(query, params).fetchall()
    conn.close()

    keys = ["id", "name", "summary", "distance", "time", "grade", "bog", "start"]
    results = [dict(zip(keys, row)) for row in rows]

    return jsonify(results), 200, {"Content-Type": "application/json; charset=utf-8"}


if __name__ == "__main__":
    app.run(debug=True)
