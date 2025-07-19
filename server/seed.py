import json
import sqlite3

# Load the JSON file with explicit UTF-8 encoding
with open("munro_descriptions.json", encoding="utf-8") as f:
    data = json.load(f)

# Create the SQLite database
conn = sqlite3.connect("db.sqlite")
c = conn.cursor()

# Ensure the database stores text correctly
conn.text_factory = str  # default is already UTF-8

# Create table
c.execute("""
  CREATE TABLE IF NOT EXISTS munros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, summary TEXT, distance REAL,
    time REAL, grade INTEGER, bog INTEGER, start TEXT
  )
""")

# Insert each record
for m in data:
    c.execute(
        "INSERT INTO munros (name, summary, distance, time, grade, bog, start) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            m["name"],
            m["summary"],
            m["distance"],
            m["time"],
            m["grade"],
            m["bog"],
            m["start"],
        ),
    )

conn.commit()
print("✅ Seeded database successfully.")
