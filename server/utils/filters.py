import re
from typing import Optional, Dict

_MILES_TO_KM = 1.60934

# Recognize things like:
# "at least 15km", ">= 15 km", "15km+", "over 10 miles"
# "at most 8km", "<= 8 km", "under 5 mi", "less than 12km"
# "between 10 and 15 km", "10-15km"
DIST_PATTERNS = [
    # between X and Y
    r"between\s+(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)\s+and\s+(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)",
    r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)",
    # min
    r"(?:at\s+least|>=|more\s+than|over)\s+(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)",
    r"(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)\s*\+",
    # max
    r"(?:at\s+most|<=|less\s+than|under)\s+(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres|mi|mile|miles)",
]

TIME_PATTERNS = [
    # between X and Y hours
    r"between\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\s+and\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)",
    r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)",
    # min
    r"(?:at\s+least|>=|more\s+than|over)\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)",
    r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\s*\+",
    # max
    r"(?:at\s+most|<=|less\s+than|under)\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)",
]


def _to_km(value: float, unit: str) -> float:
    u = unit.lower()
    if u.startswith("km") or "kilomet" in u:
        return value
    # miles/mi/mile
    return value * _MILES_TO_KM


def _to_hours(value: float, unit: str) -> float:
    # all time units above are hours already
    return value


def parse_numeric_filters(text: str) -> Dict[str, float]:
    """
    Returns a dict possibly containing:
      - distance_min_km, distance_max_km
      - time_min_h, time_max_h
    """
    s = (text or "").lower()
    out: Dict[str, float] = {}

    # distance
    for pat in DIST_PATTERNS:
        m = re.search(pat, s)
        if not m:
            continue
        if pat.startswith("between"):
            v1, u1, v2, u2 = (
                float(m.group(1)),
                m.group(2),
                float(m.group(3)),
                m.group(4),
            )
            d1, d2 = _to_km(v1, u1), _to_km(v2, u2)
            out["distance_min_km"] = min(d1, d2)
            out["distance_max_km"] = max(d1, d2)
            break
        elif " - " in pat or r"\s*-\s*" in pat:
            v1, v2, u = float(m.group(1)), float(m.group(2)), m.group(3)
            d1, d2 = _to_km(v1, u), _to_km(v2, u)
            out["distance_min_km"] = min(d1, d2)
            out["distance_max_km"] = max(d1, d2)
            break
        elif (
            "at least" in pat
            or ">=" in pat
            or "more than" in pat
            or "over" in pat
            or pat.endswith(r"\s*\+")
        ):
            v, u = float(m.group(1)), m.group(2)
            out["distance_min_km"] = _to_km(v, u)
            break
        else:
            # max
            v, u = float(m.group(1)), m.group(2)
            out["distance_max_km"] = _to_km(v, u)
            break

    # time
    for pat in TIME_PATTERNS:
        m = re.search(pat, s)
        if not m:
            continue
        if pat.startswith("between"):
            v1, u1, v2, u2 = (
                float(m.group(1)),
                m.group(2),
                float(m.group(3)),
                m.group(4),
            )
            t1, t2 = _to_hours(v1, u1), _to_hours(v2, u2)
            out["time_min_h"] = min(t1, t2)
            out["time_max_h"] = max(t1, t2)
            break
        elif " - " in pat or r"\s*-\s*" in pat:
            v1, v2, u = float(m.group(1)), float(m.group(2)), m.group(3)
            t1, t2 = _to_hours(v1, u), _to_hours(v2, u)
            out["time_min_h"] = min(t1, t2)
            out["time_max_h"] = max(t1, t2)
            break
        elif (
            "at least" in pat
            or ">=" in pat
            or "more than" in pat
            or "over" in pat
            or pat.endswith(r"\s*\+")
        ):
            v, u = float(m.group(1)), m.group(2)
            out["time_min_h"] = _to_hours(v, u)
            break
        else:
            v, u = float(m.group(1)), m.group(2)
            out["time_max_h"] = _to_hours(v, u)
            break

    return out
