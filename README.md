# Smart Energy Microgrid & Demand Forecasting Engine (HackSphere 3.0)

Live app: https://microgrid-app-50047145916.development.catalystappsail.in

A web app on **Zoho Catalyst** that forecasts hourly energy demand with a **QuickML** regression
model, decides between **Main Grid** and **Renewable Battery Storage**, and shows the plan on a dashboard.

## How it works
1. **Input**: a live form, a CSV upload, or a sample day (`timestamp, ambient_temp_c, humidity_pct, solar_irradiance_wm2`).
2. **Cleaning** (`app.py`): unreadable timestamps and duplicate timestamps are dropped, rows are sorted,
   non-numeric weather values become blanks and are filled with the column median, humidity is clipped to 0-100,
   irradiance to 0 or more, and at most 168 hourly rows are used.
3. **Features** (`features.py`): one function used everywhere. Six model inputs: `hour_profile` (average demand for that
   hour, from the training data), `is_peak` (hour 18-22 inclusive), `ambient_temp_c`, `cool_deg` (degrees above 24 C),
   `humidity_pct`, `solar_irradiance_wm2`.
4. **Forecast** (`predict.py`): calls the published QuickML endpoint (OAuth token refreshed automatically) and returns one
   kW value per row. If the endpoint fails it raises an error; it never returns made-up numbers.
5. **Transition controller** (`controller.py`), per forecast hour:
   - demand > 160 kW **or** hour 18:00-22:00 inclusive -> **Renewable Storage Mode**
   - otherwise -> **Main Grid Mode**
   - demand >= 200 kW -> **Critical Overload Alert** (independent of mode)
6. **Dashboard** (`static/index.html`): load curve with 160/200 kW lines, active mode badge, battery state of charge,
   dispatch table, system log and alert banners.

## Model
QuickML AutoML regression pipeline trained on `train_telemetry.csv` with the features above
(imputation, scaling, feature selection and PCA are applied by the pipeline). QuickML reported RMSE 8.34 kW, R2 0.97
on its own validation split. Published as a QuickML endpoint and called through `predict.py`.

## Battery assumptions
The problem statement does not define state of charge, so it is simulated (all values are in `controller.py`):
capacity 3000 kWh, starts at 80 percent (editable in the UI), Renewable mode discharges min(demand, 150 kW) per hour,
Main Grid mode recharges 100 kW per hour, clamped to 0-100 percent. Rules always follow the table above; if the battery
runs empty a warning is shown but the mode is not changed.

## Run locally
```
pip install -r requirements.txt
cp your .env next to app.py   # see settings below
python3 app.py                # http://localhost:9000
python3 test_controller.py    # rule tests
python3 predict.py --input sample_test_input.csv --output predictions.csv
```

## Settings (environment variables - keep secret, never commit)
`predict.py` reads these from the environment or a private `.env` file:

| Local `.env` name | Name on Catalyst | Meaning |
|---|---|---|
| `ZOHO_ACCOUNTS_URL` | `MG_ACCOUNTS_URL` | Zoho OAuth token URL (India data center: accounts.zoho.in) |
| `ZOHO_CLIENT_ID` | `MG_CLIENT_ID` | Self Client ID |
| `ZOHO_CLIENT_SECRET` | `MG_CLIENT_SECRET` | Self Client secret |
| `ZOHO_REFRESH_TOKEN` | `MG_REFRESH_TOKEN` | Refresh token (scope `QuickML.deployment.READ`) |
| `QUICKML_ENDPOINT_URL` | `MG_ENDPOINT_URL` | Published QuickML endpoint URL |
| `QUICKML_ENDPOINT_KEY` | `MG_ENDPOINT_KEY` | QuickML endpoint key |
| `CATALYST_ORG` | `MG_ORG` | Catalyst org ID |
| `CATALYST_ENVIRONMENT` | `MG_ENV` | `Development` or `Production` |

Catalyst rejects names starting with ZOHO_ / CATALYST_, so the deployed app uses the `MG_*` names; `predict.py` maps them back.
`app-config.example.json` shows the shape with placeholders.

## Deploy to Catalyst AppSail
```
pip install -r requirements.txt -t .     # bundle libraries
python3 make_app_config.py               # copies .env into app-config.json (private)
catalyst deploy
```

## Project layout
`app.py` backend and API, `features.py` features, `predict.py` QuickML client, `controller.py` rules and battery,
`static/` dashboard, `test_controller.py` tests, `app-config.example.json` deployment template.
