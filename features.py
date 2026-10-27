"""
features.py - the ONE place where model features are defined (pure Python, no pandas).

Used by predict.py and the Catalyst backend. The QuickML model was trained on
exactly these six columns, so this recipe must not change.
"""
import math
import statistics
from datetime import datetime

HOUR_PROFILE = {
    0: 92.37, 1: 91.88, 2: 91.8, 3: 90.83, 4: 91.5, 5: 91.79,
    6: 136.06, 7: 177.27, 8: 181.12, 9: 186.48, 10: 159.43, 11: 163.7,
    12: 165.26, 13: 170.21, 14: 172.38, 15: 171.04, 16: 172.99, 17: 171.32,
    18: 220.59, 19: 217.82, 20: 215.02, 21: 209.41, 22: 204.7, 23: 114.79,
}

FEATURE_COLUMNS = [
    "hour_profile", "is_peak", "ambient_temp_c",
    "cool_deg", "humidity_pct", "solar_irradiance_wm2",
]
WEATHER = ["ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]

_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M")


def parse_ts(value):
    """Return a naive datetime, or None if the value can't be read."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_float(value):
    """Number or None (blank, text, NaN and infinity all become None)."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def add_features(rows):
    """rows: list of dicts with timestamp + 3 weather columns.
    Returns a list of dicts with the six model features, same order as rows."""
    fills = {}
    for c in WEATHER:
        vals = [v for v in (to_float(r.get(c)) for r in rows) if v is not None]
        fills[c] = statistics.median(vals) if vals else 0.0

    out = []
    for r in rows:
        ts = parse_ts(r["timestamp"])
        if ts is None:
            raise ValueError(f"Unreadable timestamp: {r['timestamp']!r}")
        w = {}
        for c in WEATHER:
            v = to_float(r.get(c))
            w[c] = fills[c] if v is None else v
        w["humidity_pct"] = min(100.0, max(0.0, w["humidity_pct"]))
        w["solar_irradiance_wm2"] = max(0.0, w["solar_irradiance_wm2"])
        h = ts.hour
        out.append({
            "hour_profile": float(HOUR_PROFILE[h]),
            "is_peak": 1 if 18 <= h <= 22 else 0,
            "ambient_temp_c": w["ambient_temp_c"],
            "cool_deg": max(0.0, w["ambient_temp_c"] - 24.0),
            "humidity_pct": w["humidity_pct"],
            "solar_irradiance_wm2": w["solar_irradiance_wm2"],
        })
    return out
