from typing import List, Dict, Any
from db import get_db


def list_munros(grade=None, bog=None, search=None, mid=None) -> List[Dict[str, Any]]:
    """Retrieve Munros filtered by grade/bog/search/id criteria."""

    base_sql = "SELECT * FROM munros WHERE 1=1"
    clauses, params = [], []

    if mid is not None:
        clauses.append("AND id = ?")
        params.append(mid)
    if grade is not None:
        clauses.append("AND grade = ?")
        params.append(grade)
    if bog is not None:
        clauses.append("AND bog <= ?")
        params.append(bog)
    if search:
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

    out = []
    for r in rows:
        d = dict(r)
        d.pop("normalized_name", None)
        out.append(d)
    return out


def get_munro(mid: int) -> Dict[str, Any] | None:
    """Fetch a single Munro row by id, omitting internal fields."""

    with get_db() as conn:
        row = conn.execute("SELECT * FROM munros WHERE id = ?", (mid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d.pop("normalized_name", None)
    return d


def list_tags_with_counts() -> List[Dict[str, Any]]:
    """Return all tags with their usage frequency for filter displays."""

    with get_db() as conn:
        rows = conn.execute("""
            SELECT tag, COUNT(*) AS n
            FROM munro_tags
            GROUP BY tag
            ORDER BY n DESC, tag ASC
        """).fetchall()
    return [{"tag": r["tag"], "count": r["n"]} for r in rows]
