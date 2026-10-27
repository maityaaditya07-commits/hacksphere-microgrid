"""Fills app-config.json (start command + settings) from your private .env.
Prints only the NAMES of the settings it copied, never the values.
NOTE: app-config.json then contains secrets. Never commit or share it."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
keys = ["ZOHO_ACCOUNTS_URL", "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN",
        "QUICKML_ENDPOINT_URL", "QUICKML_ENDPOINT_KEY", "CATALYST_ORG", "CATALYST_ENVIRONMENT"]
env = {}
with open(os.path.join(here, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
cfg_path = os.path.join(here, "app-config.json")
cfg = json.load(open(cfg_path))
cfg["command"] = "python3 app.py"
# Catalyst rejects reserved-looking names (ZOHO_*, CATALYST_*), so use neutral MG_* names.
rename = {"ZOHO_ACCOUNTS_URL": "MG_ACCOUNTS_URL", "ZOHO_CLIENT_ID": "MG_CLIENT_ID",
          "ZOHO_CLIENT_SECRET": "MG_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN": "MG_REFRESH_TOKEN",
          "QUICKML_ENDPOINT_URL": "MG_ENDPOINT_URL", "QUICKML_ENDPOINT_KEY": "MG_ENDPOINT_KEY",
          "CATALYST_ORG": "MG_ORG", "CATALYST_ENVIRONMENT": "MG_ENV"}
cfg["env_variables"] = {rename[k]: env[k] for k in keys if k in env}
json.dump(cfg, open(cfg_path, "w"), indent=2)
print("Copied:", ", ".join(cfg["env_variables"]))
print("Missing:", ", ".join(k for k in keys if k not in env) or "none")
