import json
import sqlite3
import unicodedata
import re
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = "db.sqlite"
JSON_PATH = "munro_descriptions.json"


# ---------- Helpers ----------
def fix_mojibake(s: str) -> str:
    """Repair common mojibake sequences produced by mis-decoded text."""
    if not isinstance(s, str):
        return s
    try:
        repaired = s.encode("latin-1", "ignore").decode("utf-8", "ignore")
        if ("Ã" in s or "Â" in s) and (("Ã" not in repaired) and ("Â" not in repaired)):
            return repaired
    except Exception:
        pass
    return s


def to_nfc(s: str) -> str:
    """Normalise Unicode strings into NFC form."""
    return unicodedata.normalize("NFC", s or "")


APOS = {"\u2019": "'", "\u2018": "'", "\u2032": "'", "\u02bc": "'"}
DASH = {"\u2013": "-", "\u2014": "-", "\u2212": "-"}


def clean_text(s: Any) -> Any:
    """Apply mojibake fixes and replace troublesome punctuation."""
    if not isinstance(s, str):
        return s
    s = fix_mojibake(s)
    s = to_nfc(s)
    for k, v in APOS.items():
        s = s.replace(k, v)
    for k, v in DASH.items():
        s = s.replace(k, v)
    return s


def clean_gpx(path: Any) -> Any:
    """Normalise GPX file paths to forward slashes."""
    if not isinstance(path, str):
        return path
    return path.replace("\\", "/")


def snake(s: str) -> str:
    """Convert arbitrary strings into safe snake_case column names."""
    # lower, replace non-alnum with _, collapse, trim
    s = re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    if not s:
        s = "field"
    return s


def canonicalize_name(name: str) -> str:
    """Return a cleaned display name for a Munro."""
    s = clean_text(name)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonical_key(name: str) -> str:
    """Create a case-insensitive key suitable for deduplicating names."""
    s = canonicalize_name(name)
    s = s.casefold()
    # unify apostrophes/dashes in key
    s = (
        s.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )
    return s


def infer_sql_type(values: List[Any]) -> str:
    """Infer a reasonable SQLite type from the dataset: INTEGER, REAL, TEXT."""
    has_text = False
    has_real = False
    has_int = True
    for v in values:
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            has_text = True  # store as TEXT/INTEGER? safer to treat as TEXT for now
            continue
        if isinstance(v, (int,)):
            continue
        if isinstance(v, float):
            has_int = False
            has_real = True
            continue
        # strings: try numeric parse
        if isinstance(v, str):
            vs = v.strip()
            if vs == "":
                continue
            try:
                int(vs)
            except Exception:
                try:
                    float(vs)
                    has_int = False
                    has_real = True
                except Exception:
                    has_text = True
            continue
        # any other type -> TEXT
        has_text = True
    if has_text:
        return "TEXT"
    if has_real and not has_text:
        return "REAL"
    if has_int and not has_text and not has_real:
        return "INTEGER"
    # default
    return "TEXT"


# ---------- Load & sanitize JSON ----------
raw = json.loads(Path(JSON_PATH).read_text(encoding="utf-8"))

# Sanitize keys and values; build records & dedupe by canonical key
records: List[Dict[str, Any]] = []
for row in raw:
    if not isinstance(row, dict):
        continue
    sanitized: Dict[str, Any] = {}
    for k, v in row.items():
        sk = snake(k)
        if sk == "name":
            sanitized[sk] = canonicalize_name(str(v or ""))
        elif sk == "gpx_file":
            sanitized[sk] = clean_gpx(clean_text(v))
        else:
            sanitized[sk] = clean_text(v) if isinstance(v, str) else v
    # name is required
    name = sanitized.get("name") or ""
    sanitized["name"] = canonicalize_name(name)
    sanitized["normalized_name"] = canonical_key(sanitized["name"])
    records.append(sanitized)

# Deduplicate by normalized_name (merge: longer summary/description, first non-null numerics, prefer non-empty text)
merged: Dict[str, Dict[str, Any]] = {}
for r in records:
    key = r["normalized_name"]
    if key not in merged:
        merged[key] = r
    else:
        cur = merged[key]
        # prefer longer text fields
        for tf in ("summary", "description", "start", "terrain", "public_transport"):
            if r.get(tf) and (len(str(r.get(tf))) > len(str(cur.get(tf) or ""))):
                cur[tf] = r[tf]
        # prefer non-empty gpx_file/url
        for tf in ("gpx_file", "url", "route_url"):
            if not cur.get(tf) and r.get(tf):
                cur[tf] = r[tf]
        # pick numerics if missing in current
        for nf in ("distance", "time", "grade", "bog"):
            if cur.get(nf) in (
                None,
                "",
            ) and r.get(nf) not in (
                None,
                "",
            ):
                cur[nf] = r[nf]

rows = list(merged.values())

# Determine superset of columns from JSON (sanitized), excluding internal id
all_keys = set()
for r in rows:
    all_keys.update(r.keys())

# Ensure name + normalized_name present
all_keys.add("name")
all_keys.add("normalized_name")

# Order columns: id, name, normalized_name, then the rest sorted
ordered_cols = ["id", "name", "normalized_name"] + sorted(
    k for k in all_keys if k not in {"id", "name", "normalized_name"}
)

# Infer types for each non-internal column (except id)
col_types: Dict[str, str] = {}
for col in ordered_cols:
    if col in ("id",):
        continue
    if col == "normalized_name":
        col_types[col] = "TEXT"
        continue
    values = [r.get(col) for r in rows]
    col_types[col] = infer_sql_type(values)

# Build table
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS munros")

cols_ddl = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
for col in ordered_cols:
    if col == "id":
        continue
    # ensure name & normalized_name constraints
    if col == "name":
        cols_ddl.append("name TEXT NOT NULL")
        continue
    if col == "normalized_name":
        cols_ddl.append("normalized_name TEXT NOT NULL UNIQUE")
        continue
    cols_ddl.append(f"{col} {col_types[col]}")

ddl = f"CREATE TABLE munros ({', '.join(cols_ddl)})"
c.execute(ddl)

# Insert rows
insert_cols = [col for col in ordered_cols if col != "id"]
placeholders = ", ".join("?" for _ in insert_cols)
sql = f"INSERT INTO munros ({', '.join(insert_cols)}) VALUES ({placeholders})"

vals = []
for r in rows:
    row_vals = []
    for col in insert_cols:
        v = r.get(col)
        if col == "gpx_file" and isinstance(v, str):
            v = clean_gpx(v)
        if isinstance(v, str):
            v = clean_text(v)
        row_vals.append(v)
    vals.append(tuple(row_vals))

c.executemany(sql, vals)
conn.commit()
conn.close()

print(
    f"✅ Seeded {len(rows)} unique munros with ALL JSON fields (keys sanitized to snake_case)."
)
