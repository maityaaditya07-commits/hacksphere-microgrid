"""
app.py - Smart Energy Microgrid web app (Flask).

Serves the dashboard (static/index.html) and a small JSON API:
    GET  /api/health     -> {"status": "ok"}
    GET  /api/sample     -> a ready-made 24-hour weather window
    POST /api/forecast   -> JSON {"rows": [...]} or a CSV file upload ("file")
                            returns demand forecast + grid dispatch plan

Run locally:  python3 app.py     then open http://localhost:9000
On Catalyst AppSail the port comes from X_ZOHO_CATALYST_LISTEN_PORT.
"""
import csv
import io
import os

from flask import Flask, jsonify, request, send_from_directory

import predict as model_client          # calls the published QuickML endpoint
from controller import Battery, build_plan, summarize
from features import parse_ts, to_float

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")

WEATHER_COLS = ["ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]
REQUIRED = ["timestamp"] + WEATHER_COLS
MAX_ROWS = 168  # one week of hourly rows


class InputError(Exception):
    pass


def clean_rows(rows):
    """Validate + clean raw telemetry (list of dicts). Returns (clean_rows, report)."""
    norm = [{str(k).strip().lower(): v for k, v in r.items()} for r in rows if isinstance(r, dict)]
    present = set().union(*[r.keys() for r in norm]) if norm else set()
    missing_cols = [c for c in REQUIRED if c not in present]
    if missing_cols:
        raise InputError("Missing column(s): " + ", ".join(missing_cols))
    report = {"rows_received": len(norm)}

    parsed, bad_ts = [], 0
    for r in norm:
        ts = parse_ts(r.get("timestamp"))
        if ts is None:
            bad_ts += 1
            continue
        parsed.append((ts, r))
    report["rows_dropped_bad_timestamp"] = bad_ts

    unique = {}
    for ts, r in parsed:           # later rows win, like keep="last"
        unique[ts] = r
    report["rows_dropped_duplicate_timestamp"] = len(parsed) - len(unique)

    clean, filled = [], 0
    for ts in sorted(unique):
        r = unique[ts]
        row = {"timestamp": ts}
        for c in WEATHER_COLS:
            v = to_float(r.get(c))
            if v is None:
                filled += 1
            row[c] = v
        clean.append(row)
    report["values_filled"] = filled  # features.py fills these with the column median

    if not clean:
        raise InputError("No usable rows found. Check the timestamp format (YYYY-MM-DD HH:MM:SS).")
    if len(clean) > MAX_ROWS:
        report["rows_truncated"] = len(clean) - MAX_ROWS
        clean = clean[:MAX_ROWS]
    report["rows_used"] = len(clean)
    return clean, report


def run_pipeline(rows, battery: Battery):
    clean, report = clean_rows(rows)
    preds = model_client.predict(clean)          # raises if the endpoint fails (no fake numbers)
    plan = build_plan([r["timestamp"] for r in clean], preds, battery)
    return {"cleaning": report, "plan": plan, "summary": summarize(plan)}


def battery_from(payload) -> Battery:
    b = Battery()
    try:
        soc = float(payload.get("initial_soc_pct", b.initial_soc_pct))
        b.initial_soc_pct = min(100.0, max(0.0, soc))
    except (TypeError, ValueError):
        pass
    return b


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/sample")
def sample():
    path = os.path.join(HERE, "sample_test_input.csv")
    if not os.path.exists(path):
        return jsonify(error="sample data file not found on server"), 404
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    start = 0                                    # first 00:00 row
    for i, r in enumerate(rows):
        ts = parse_ts(r["timestamp"])
        if ts is not None and ts.hour == 0:
            start = i
            break
    window = []
    for r in rows[start:start + 24]:
        item = {"timestamp": r["timestamp"]}
        for c in WEATHER_COLS:
            item[c] = to_float(r.get(c))
        window.append(item)
    return jsonify(rows=window)


@app.post("/api/forecast")
def forecast():
    try:
        if "file" in request.files:
            raw = request.files["file"].read().decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(raw))
            if not reader.fieldnames:
                raise InputError("That file is not a readable CSV.")
            rows = list(reader)
            battery = battery_from(request.form)
        else:
            payload = request.get_json(silent=True) or {}
            rows = payload.get("rows")
            if not rows:
                raise InputError("Send at least one row, or upload a CSV file.")
            battery = battery_from(payload)
        return jsonify(run_pipeline(rows, battery))
    except InputError as e:
        return jsonify(error=str(e)), 400
    except csv.Error:
        return jsonify(error="That file is not a readable CSV."), 400
    except Exception as e:  # model/endpoint problems: say so, never invent numbers
        return jsonify(error=f"Forecast failed: {e}"), 502


if __name__ == "__main__":
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    app.run(host="0.0.0.0", port=port)
