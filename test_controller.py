"""Run:  python3 test_controller.py   (prints OK if all rules behave)"""
import pandas as pd
from controller import decide, build_plan, summarize, RENEWABLE, MAIN_GRID, Battery


def check(demand, hour, mode, overload):
    r = decide(demand, hour)
    assert r["grid_mode"] == mode and r["overload"] == overload, (demand, hour, r)


# threshold edge: exactly 160 is NOT "above 160"
check(160.0, 12, MAIN_GRID, False)
check(160.01, 12, RENEWABLE, False)
# peak window 18..22 inclusive, even with tiny demand
check(50, 17, MAIN_GRID, False)
check(50, 18, RENEWABLE, False)
check(50, 22, RENEWABLE, False)
check(50, 23, MAIN_GRID, False)
# overload at >= 200, independent of mode
check(199.99, 12, RENEWABLE, False)
check(200.0, 12, RENEWABLE, True)
check(250, 20, RENEWABLE, True)

# battery: discharges in renewable mode, recharges on grid, stays within 0..100
ts = list(pd.date_range("2026-01-01 00:00", periods=24, freq="h"))
plan = build_plan(ts, [100] * 6 + [250] * 18, Battery())
assert all(0 <= p["soc_pct"] <= 100 for p in plan)
assert plan[0]["soc_pct"] == 83.3          # 80 % + 100 kWh recharge on a 3000 kWh battery
assert plan[6]["soc_pct"] < plan[5]["soc_pct"]  # discharging
s = summarize(plan)
assert s["renewable_hours"] + s["main_grid_hours"] == 24
assert s["overload_hours"] == 18
assert s["events"][0]["signal"].startswith("Switch to")
print("OK - all controller tests passed")
