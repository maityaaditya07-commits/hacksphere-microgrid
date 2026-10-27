"""
predict.py - HackSphere 3.0 demand forecaster client.

Takes rows of [timestamp, ambient_temp_c, humidity_pct, solar_irradiance_wm2],
builds the model features (features.py), calls the published QuickML endpoint
and returns one predicted demand (kW) per row.

Credentials are NEVER stored in this file. They come from environment variables
or from a private .env file next to this script (see README.md):
    ZOHO_ACCOUNTS_URL, ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    QUICKML_ENDPOINT_URL, QUICKML_ENDPOINT_KEY, CATALYST_ORG, CATALYST_ENVIRONMENT

Usage:
    python predict.py --input sample_test_input.csv --output predictions.csv
"""
import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

import csv

import requests

from features import add_features

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOKEN = {"value": None, "expires": 0.0}
_ALIASES = {
    "MG_ACCOUNTS_URL": "ZOHO_ACCOUNTS_URL",
    "MG_CLIENT_ID": "ZOHO_CLIENT_ID",
    "MG_CLIENT_SECRET": "ZOHO_CLIENT_SECRET",
    "MG_REFRESH_TOKEN": "ZOHO_REFRESH_TOKEN",
    "MG_ENDPOINT_URL": "QUICKML_ENDPOINT_URL",
    "MG_ENDPOINT_KEY": "QUICKML_ENDPOINT_KEY",
    "MG_ORG": "QUICKML_ORG",
    "MG_ENV": "QUICKML_ENV",
}


def _load_env():
    """Read KEY=VALUE lines from .env (if present). Real environment variables win."""
    path = os.path.join(_HERE, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    # On Catalyst the settings arrive under neutral MG_* names (the platform rejects
    # ZOHO_*/CATALYST_* names); map them back to the names used in this file.
    for alias, real in _ALIASES.items():
        if os.environ.get(alias):
            os.environ.setdefault(real, os.environ[alias])


def _need(name):
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing setting {name}. Put it in .env or set it as an environment variable."
        )
    return val


def _access_token():
    """Short-lived Zoho access token, refreshed automatically (cached ~50 min)."""
    if _TOKEN["value"] and time.time() < _TOKEN["expires"]:
        return _TOKEN["value"]
    r = requests.post(
        _need("ZOHO_ACCOUNTS_URL"),
        data={
            "grant_type": "refresh_token",
            "client_id": _need("ZOHO_CLIENT_ID"),
            "client_secret": _need("ZOHO_CLIENT_SECRET"),
            "refresh_token": _need("ZOHO_REFRESH_TOKEN"),
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if "access_token" not in body:
        raise RuntimeError(f"Could not get access token from Zoho: {body}")
    _TOKEN["value"] = body["access_token"]
    _TOKEN["expires"] = time.time() + 50 * 60
    return _TOKEN["value"]


def _headers():
    return {
        "Content-Type": "application/json",
        "X-QUICKML-ENDPOINT-KEY": _need("QUICKML_ENDPOINT_KEY"),
        "Authorization": f"Zoho-oauthtoken {_access_token()}",
        "CATALYST-ORG": os.environ.get("QUICKML_ORG") or _need("CATALYST_ORG"),
        "Environment": os.environ.get("QUICKML_ENV") or os.environ.get("CATALYST_ENVIRONMENT", "Development"),
    }


def _post(data, retries=3):
    """POST {"data": data} to the endpoint, retrying on temporary failures."""
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(
                _need("QUICKML_ENDPOINT_URL"),
                headers=_headers(),
                json={"data": data},
                timeout=60,
            )
            if r.status_code == 401:  # token went stale; force a refresh and retry
                _TOKEN["value"] = None
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"QuickML endpoint call failed after {retries} tries: {last}")


def _to_floats(result):
    return [float(x) for x in result]


def _predict_one(record):
    return _to_floats(_post(record)["result"])[0]


def predict(rows):
    """
    Parameters:
        rows: a pandas DataFrame (what the grader passes) OR a list of dicts, with columns
              'timestamp', 'ambient_temp_c', 'humidity_pct', 'solar_irradiance_wm2'
    Returns:
        numpy array of predicted demand (kW) when numpy is installed, otherwise a list of
        floats; one value per input row, same order.
    """
    _load_env()
    if hasattr(rows, "to_dict"):                 # DataFrame -> list of dicts
        rows = rows.to_dict(orient="records")
    records = add_features(rows)
    n = len(records)

    out = None
    # Fast path: send all rows in one request (if the endpoint accepts a list).
    try:
        res = _to_floats(_post(records, retries=1)["result"])
        if len(res) == n:
            out = res
    except Exception:  # noqa: BLE001
        pass  # fall through to the safe row-by-row path

    # Safe path: one request per row, several in parallel, order preserved.
    if out is None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            out = list(pool.map(_predict_one, records))

    try:
        import numpy as np
        return np.array(out, dtype=float)
    except ImportError:                          # e.g. on Catalyst, where numpy is not bundled
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="sample_test_input.csv")
    ap.add_argument("--output", default="predictions.csv")
    args = ap.parse_args()

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    preds = predict(rows)
    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "target_demand_kw"])
        for r, p in zip(rows, preds):
            w.writerow([r["timestamp"], f"{p:.2f}"])
    print(f"Wrote {len(preds)} predictions to {args.output}")


if __name__ == "__main__":
    main()
