import re, unicodedata
from typing import List, Dict

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "in",
    "on",
    "by",
    "for",
    "with",
    "at",
    "from",
    "near",
}

GENERIC_SYNONYMS: Dict[str, list[str]] = {
    "scramble": ["scramble", "scrambling"],
    "scrambles": ["scramble", "scrambling"],
    "airy": ["airy", "exposed", "exposure"],
    "bus": ["bus", "buses"],
    "train": ["train", "rail", "railway", "station"],
}

DIFF_WORD_TO_NUM = {
    "easy": 3,
    "moderate": 4,
    "hard": 5,
    "serious": 5,
}


def tokenize(q: str) -> List[str]:
    return [t for t in re.split(r"[^\w']+", (q or "").lower()) if t]


def quote_or_prefix(term: str) -> str:
    if " " in term:
        return f'"{term}"'
    return f"{term[:5]}*" if len(term) >= 5 else term


def expand_query_for_fts(q: str) -> str:
    toks = tokenize(q)
    candidates: list[str] = []
    for t in toks:
        if t in STOPWORDS:
            continue
        candidates.extend(GENERIC_SYNONYMS.get(t, [t]))

    seen, cleaned = set(), []
    for s in candidates:
        s = s.strip()
        k = s.lower()
        if s and k not in seen:
            seen.add(k)
            cleaned.append(s)

    terms = [quote_or_prefix(s) for s in cleaned]
    return " OR ".join(terms) if terms else ""


def build_like_terms(q: str) -> list[str]:
    toks = tokenize(q)
    expanded: list[str] = []
    for t in toks:
        if t in STOPWORDS:
            continue
        expanded.extend(GENERIC_SYNONYMS.get(t, [t]))

    seen, out = set(), []
    for t in expanded:
        t = t.strip()
        k = t.lower()
        if t and k not in seen:
            seen.add(k)
            out.append(f"%{t}%")
    return out[:12]


def normalize_grade_max(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v.isdigit():
            n = int(v)
            return n if n >= 3 else 3
        return DIFF_WORD_TO_NUM.get(v)
    try:
        n = int(value)
        return n if n >= 3 else 3
    except Exception:
        return None


def norm_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()
