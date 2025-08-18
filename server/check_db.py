import sqlite3

conn = sqlite3.connect("db.sqlite")
c = conn.cursor()

rows = c.execute("SELECT id, name FROM munros WHERE name LIKE 'Aonach%'").fetchall()
for r in rows:
    print(r)

conn.close()
