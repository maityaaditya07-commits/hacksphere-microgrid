"""
controller.py - Transition Controller + battery simulation (pure Python, no web code).

RULES (problem statement, section 6), evaluated per forecast hour:
  * demand > 160 kW  OR  hour is 18..22 inclusive  ->  Renewable Storage Mode
  * otherwise                                       ->  Main Grid Mode
  * demand >= 200 kW                                ->  Critical Overload Alert
    (the alert is independent of the grid mode)

BATTERY ASSUMPTIONS (the problem statement does not define state-of-charge, so
we simulate it; all numbers are documented in README.md and easy to change):
  * capacity 3000 kWh, starts at 80 %
  * every forecast row is one hour
  * Renewable Storage Mode: battery discharges min(demand, 150 kW) for the hour
  * Main Grid Mode: battery recharges at 100 kW for the hour
  * state of charge is clamped to 0..100 %
  * the grid mode always follows the rules above; if the battery runs empty
    while the rules ask for Renewable mode we only raise a 'battery_empty' flag.
"""
from dataclasses import dataclass

HIGH_DEMAND_KW = 160.0
OVERLOAD_KW = 200.0
PEAK_START_HOUR = 18
PEAK_END_HOUR = 22  # inclusive

RENEWABLE = "Renewable Storage Mode"
MAIN_GRID = "Main Grid Mode"


@dataclass
class Battery:
    capacity_kwh: float = 3000.0
    initial_soc_pct: float = 80.0
    max_discharge_kw: float = 150.0
    max_charge_kw: float = 100.0
    low_soc_pct: float = 20.0


def decide(demand_kw: float, hour: int) -> dict:
    """Apply the transition rules to ONE forecast hour."""
    in_peak_window = PEAK_START_HOUR <= hour <= PEAK_END_HOUR
    high_demand = demand_kw > HIGH_DEMAND_KW
    if high_demand or in_peak_window:
        mode = RENEWABLE
        reason = "demand above 160 kW" if high_demand else "evening peak window (18:00-22:00)"
        if high_demand and in_peak_window:
            reason = "demand above 160 kW and evening peak window"
    else:
        mode = MAIN_GRID
        reason = "demand at or below 160 kW, outside peak window"
    return {
        "grid_mode": mode,
        "reason": reason,
        "overload": demand_kw >= OVERLOAD_KW,
    }


def build_plan(timestamps, demands_kw, battery: Battery = None) -> list:
    """Dispatch plan for a whole forecast window, including battery state of charge."""
    battery = battery or Battery()
    soc_kwh = battery.capacity_kwh * battery.initial_soc_pct / 100.0
    plan = []
    for ts, demand in zip(timestamps, demands_kw):
        demand = float(demand)
        d = decide(demand, ts.hour)
        battery_empty = False
        if d["grid_mode"] == RENEWABLE:
            wanted = min(demand, battery.max_discharge_kw)  # kW for 1 h = kWh
            drawn = min(wanted, soc_kwh)
            battery_empty = drawn < wanted
            soc_kwh -= drawn
        else:
            soc_kwh = min(battery.capacity_kwh, soc_kwh + battery.max_charge_kw)
        soc_pct = round(100.0 * soc_kwh / battery.capacity_kwh, 1)
        plan.append(
            {
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "hour": int(ts.hour),
                "predicted_kw": round(demand, 2),
                "grid_mode": d["grid_mode"],
                "reason": d["reason"],
                "overload": d["overload"],
                "soc_pct": soc_pct,
                "battery_low": soc_pct <= battery.low_soc_pct,
                "battery_empty": battery_empty,
            }
        )
    return plan


def summarize(plan: list) -> dict:
    """Counts, alerts and mode-switch events for the dashboard log."""
    events, prev = [], None
    for row in plan:
        if row["grid_mode"] != prev:
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "signal": "Switch to " + row["grid_mode"],
                    "reason": row["reason"],
                }
            )
            prev = row["grid_mode"]
    overloads = [r["timestamp"] for r in plan if r["overload"]]
    return {
        "hours": len(plan),
        "renewable_hours": sum(r["grid_mode"] == RENEWABLE for r in plan),
        "main_grid_hours": sum(r["grid_mode"] == MAIN_GRID for r in plan),
        "overload_hours": len(overloads),
        "overload_timestamps": overloads,
        "peak_kw": max((r["predicted_kw"] for r in plan), default=0),
        "min_soc_pct": min((r["soc_pct"] for r in plan), default=0),
        "battery_empty_hours": sum(r["battery_empty"] for r in plan),
        "events": events,
    }
