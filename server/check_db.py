# preview_db.py
import sqlite3
import pandas as pd

DB_PATH = "db.sqlite"


def preview(table: str = "munros", n: int = 5):
    """Print the first *n* rows of the requested table for quick inspection."""
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT * FROM {table} LIMIT {n};"
    df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"Preview of table '{table}' (first {n} rows):")
    print(df.head(n).to_string(index=False))


if __name__ == "__main__":
    preview("munros", 1)  # Preview main table
#    preview("munro_tags", 10)  # Preview tags (if exists)
#    preview("munro_fts", 5)  # Preview FTS (if exists)
