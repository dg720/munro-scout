import json, sqlite3, unicodedata, re
from pathlib import Path

DB_PATH = "db.sqlite"
JSON_PATH = "munro_descriptions.json"


def fix_mojibake(s: str) -> str:
    if not isinstance(s, str):
        return s
    try:
        repaired = s.encode("latin-1", "ignore").decode("utf-8", "ignore")
        # Prefer the version with fewer mojibake artifacts
        bad = ("Ã", "Â")
        if sum(repaired.count(b) for b in bad) < sum(s.count(b) for b in bad):
            return repaired
    except Exception:
        pass
    return s


def to_nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# Map curly quotes/dashes to canonical ASCII
APOSTROPHE_MAP = {
    "\u2019": "'",
    "\u2018": "'",
    "\u2032": "'",
    "\u02bc": "'",
}
DASH_MAP = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
}


def canonicalize_for_key(name: str) -> str:
    s = fix_mojibake(name or "")
    s = to_nfc(s)
    # unify quotes/dashes
    for k, v in APOSTROPHE_MAP.items():
        s = s.replace(k, v)
    for k, v in DASH_MAP.items():
        s = s.replace(k, v)
    # collapse whitespace, trim, casefold
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def clean_text(s: str) -> str:
    return to_nfc(fix_mojibake(s or ""))


def clean_gpx(path: str) -> str:
    return (path or "").replace("\\", "/")  # normalize for web use


with open(JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

# Deduplicate by canonicalized name
seen = {}
records = []
for m in data:
    name = clean_text(m.get("name", ""))
    key = canonicalize_for_key(name)
    rec = {
        "name": name,
        "normalized_name": key,
        "summary": clean_text(m.get("summary", "")),
        "distance": m.get("distance"),
        "time": m.get("time"),
        "grade": m.get("grade"),
        "bog": m.get("bog"),
        "start": clean_text(m.get("start", "")),
        "gpx_file": clean_gpx(m.get("gpx_file", "")),
    }
    if key not in seen:
        seen[key] = rec
    else:
        cur = seen[key]
        # keep longer summary
        if len(rec["summary"]) > len(cur["summary"]):
            cur["summary"] = rec["summary"]
        # take first non-null numerics
        for f in ("distance", "time", "grade", "bog"):
            if cur[f] in (None, "") and rec[f] not in (None, ""):
                cur[f] = rec[f]
        # prefer longer 'start'
        if len(rec["start"]) > len(cur["start"]):
            cur["start"] = rec["start"]
        # prefer non-empty gpx_file
        if not cur["gpx_file"] and rec["gpx_file"]:
            cur["gpx_file"] = rec["gpx_file"]

records = list(seen.values())
print(f"Loaded {len(data)} → {len(records)} unique after normalization.")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Rebuild table with normalized_name UNIQUE
c.execute("DROP TABLE IF EXISTS munros")
c.execute("""
CREATE TABLE munros (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  summary TEXT,
  distance REAL,
  time REAL,
  grade INTEGER,
  bog INTEGER,
  start TEXT,
  gpx_file TEXT,
  UNIQUE(normalized_name)
)
""")

c.executemany(
    """INSERT INTO munros
       (name, normalized_name, summary, distance, time, grade, bog, start, gpx_file)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        (
            r["name"],
            r["normalized_name"],
            r["summary"],
            r["distance"],
            r["time"],
            r["grade"],
            r["bog"],
            r["start"],
            r["gpx_file"],
        )
        for r in records
    ],
)

conn.commit()
conn.close()
print("✅ Seeded with NFC-normalized names, deduped, and web-safe GPX paths.")
