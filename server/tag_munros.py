# server/tag_munros.py
import os, json, sqlite3, time
from typing import Dict, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
DB_PATH = "db.sqlite"

# --- Ontology (one-word tags; keep special 'river_crossing') ---
ONTOLOGY = {
    "terrain": [
        "ridge",
        "scramble",
        "technical",
        "steep",
        "rocky",
        "boggy",
        "heather",
        "scree",
        "handson",
        "knifeedge",
        "airy",
        "slab",
        "gully",
    ],
    "difficulty": ["easy", "moderate", "hard", "serious"],
    "nav": ["pathless"],
    "hazards": ["loose_rock", "cornice", "river_crossing", "slippery", "exposure"],
    "access": ["bus", "train", "bike"],  # transport only = bus/train/bike
    "features": [
        "classic",
        "views",
        "waterfalls",
        "bothy",
        "scrambling",
        "camping",
        "multiday",
    ],
    "crowding": ["popular", "quiet"],
    "suitability": ["family"],  # dog_ok removed
}
ALLOWED = sorted({t for v in ONTOLOGY.values() for t in v})

# --- LLM client ---
llm = ChatOpenAI(
    model="gpt-4o-mini",  # or "gpt-3.5-turbo"
    temperature=0,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

SYSTEM = (
    "You are a strict tagger for Scottish Munro routes. "
    "Use only the allowed one-word tags (except 'river_crossing'). "
    "Never invent new tags."
)

PROMPT = """Allowed tags (DO NOT add new ones):
{allowed}

ROUTE DATA
Name: {name}
Terrain (verbatim): {terrain}
Public transport (verbatim): {public_transport}
Start / access (verbatim): {start_access}
Description (excerpt): {description}

TAGGING RULES (strict & conservative)
- Use ONLY allowed tags. Tags should be one word (except 'river_crossing', 'loose_rock').
- Select **3–6 tags total**. Each tag must be clearly supported by the text above.
- 'scramble' → ONLY if actual scrambling (Grade 1+ or sustained hands-on ROCK moves). Not for steep grass, rough paths, or simple boulder fields.
- 'technical' → pitched moves OR Grade 3 scrambling / climbing elements (e.g., Cuillin peaks, Inaccessible Pinnacle).
- 'exposure' → ONLY for significant drops / precipitous narrow ridges/ledges (not weather exposure).
- 'pathless' → sustained sections without a clear made path/markers (not short detours).
- 'river_crossing' → ONLY if the text states the walker must **wade/ford** a river/stream **without a bridge/stepping stones**. 
  Do NOT add if a bridge/footbridge/stepping stones is available, or the river is merely mentioned.
- Transport tags: include 'bus' and/or 'train' if feasible/mentioned; include 'bike' if cycle access is feasible. If none are mentioned, add no transport tag.
- Consider 'camping' or 'multiday' only where wild-camping or multi-day itineraries are common/mentioned.

KEYWORDS
- Produce 10–25 short, search-friendly keywords (place names, ridges, corries, bealachs/cols, burns, lochs, bothies, huts; approach junctions; escape routes; named PT stops).
- STRICTLY EXCLUDE: 'os maps', 'os', 'ordnance survey', 'view', 'views', 'viewpoint', 'munro', 'munros'.
- Avoid filler adjectives (e.g., 'great', 'nice') and vague phrases ('car park' alone).
- No duplicates. Use commas to separate keywords. Keep each keyword 1–4 words.

OUTPUT (STRICT JSON only)
{{
  "tags": ["ridge","scramble","bus"],
  "keywords": "aonach eagach, ridge traverse, exposed arete, bus to glencoe, pap of glencoe, grade 3 scrambling, ..."
}}
"""


def filter_allowed(tags: List[str]) -> List[str]:
    return [t for t in tags if t in ALLOWED]


def llm_call_with_retry(messages: List[Dict], tries: int = 3):
    for i in range(1, tries + 1):
        try:
            return llm.invoke(messages).content
        except Exception as e:
            if i == tries:
                raise
            backoff = 0.6 * (2 ** (i - 1))  # 0.6s, 1.2s, 2.4s...
            print(
                f"    … transient LLM error ({e}); retry {i}/{tries - 1} after {backoff:.1f}s",
                flush=True,
            )
            time.sleep(backoff)


def tag_one(doc: Dict) -> Dict:
    msg = PROMPT.format(
        allowed=", ".join(ALLOWED),
        name=doc.get("name", ""),
        terrain=(doc.get("terrain", "") or "")[:800],
        public_transport=(doc.get("public_transport", "") or "")[:800],
        start_access=(doc.get("start", "") or doc.get("access", "") or "")[:800],
        description=(doc.get("description", "") or "")[:1200],
    )
    txt = (
        llm_call_with_retry(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}]
        )
        or ""
    ).strip()

    try:
        data = json.loads(txt)
    except Exception:
        data = {"tags": [], "keywords": ""}

    tags = filter_allowed(data.get("tags", []))
    return {"tags": tags, "keywords": (data.get("keywords") or "").strip()}


def ensure_aux_tables(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS munro_tags (
          munro_id INTEGER NOT NULL,
          tag TEXT NOT NULL,
          PRIMARY KEY (munro_id, tag),
          FOREIGN KEY (munro_id) REFERENCES munros(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS munro_fts USING fts5(
          name, summary, description, keywords, content=''
        )
    """)
    conn.commit()


def main(ids: List[int] = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_aux_tables(conn)
    c = conn.cursor()

    # detect available columns (avoid KeyErrors on missing fields)
    existing = {r["name"] for r in c.execute("PRAGMA table_info(munros)")}
    base_fields = [
        "name",
        "description",
        "terrain",
        "public_transport",
        "start",
        "access",
        "summary",
    ]
    selects = ["id"] + [(f if f in existing else f"'' AS {f}") for f in base_fields]

    sql = f"SELECT {', '.join(selects)} FROM munros"
    params: List = []
    if ids:
        placeholders = ",".join("?" for _ in ids)
        sql += f" WHERE id IN ({placeholders})"
        params = ids

    c.execute(sql, params)
    rows = c.fetchall()

    total = len(rows)
    print(f"Tagging {total} munros...\n")

    for i, row in enumerate(rows, start=1):
        doc = {
            k: row[k]
            for k in [
                "id",
                "name",
                "description",
                "terrain",
                "public_transport",
                "start",
                "access",
                "summary",
            ]
        }
        display = doc["name"] or f"id={doc['id']}"
        print(f"[{i}/{total}] {display} → calling LLM...", flush=True)

        try:
            out = tag_one(doc)
            tags, keywords = out["tags"], out["keywords"]

            c.execute("BEGIN")

            # 1) Upsert tags
            for t in tags:
                c.execute(
                    "INSERT OR IGNORE INTO munro_tags (munro_id, tag) VALUES (?,?)",
                    (doc["id"], t),
                )

            # 2) Contentless FTS5: 'delete' control insert, then fresh insert
            c.execute(
                "INSERT INTO munro_fts(munro_fts, rowid) VALUES ('delete', ?)",
                (doc["id"],),
            )
            c.execute(
                "INSERT INTO munro_fts(rowid,name,summary,description,keywords) VALUES (?,?,?,?,?)",
                (
                    doc["id"],
                    doc["name"] or "",
                    doc["summary"] or "",
                    doc["description"] or "",
                    keywords,
                ),
            )

            conn.commit()
            print(f"    ✓ tags={tags} | keywords_len={len(keywords)}")
            print(f"      keywords: {keywords}\n", flush=True)

        except Exception as e:
            conn.rollback()
            print(f"    ✗ error tagging {display}: {e}", flush=True)

        time.sleep(0.03)

    # optional: optimize FTS index
    try:
        c.execute("INSERT INTO munro_fts(munro_fts) VALUES ('optimize')")
        conn.commit()
    except Exception:
        pass

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    # main()               # all
    # main([1, 2, 3, 4])   # specific IDs
    main()
