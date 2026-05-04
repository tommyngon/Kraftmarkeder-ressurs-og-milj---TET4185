"""
Task 4-3 — Supply Scarcity: Wind Reduction + Compound Scenarios
================================================================
Models supply scarcity by combining:
  (a) Wind integration (Task 4-1 setup — wind reduces net demand)
  (b) Demand scaling (Task 4-2 setup — peak demand)
  (c) Dry-year hydro constraints (Nordic_dry.xlsx)

Scenarios modelled (all with FBMC unless noted):
  S1: Wet year, no wind, base demand  (reference)
  S2: Wet year, full wind, base demand
  S3: Wet year, full wind, demand x1.2  (peak + wind)
  S4: Dry year, no wind, base demand
  S5: Dry year, full wind, base demand
  S6: Dry year, full wind, demand x1.2  (compound scarcity)

Reproduces:
  Table A.13 — Supply scarcity compound scenario results

Run
---
    cd code/
    python problem4/task4_3_supply_scarcity.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../problem3"))
from nordic_base import solve_nordic, compute_congestion_rent, _read_excel

# sibling import
sys.path.insert(0, os.path.dirname(__file__))
from task4_1_wind_integration import WIND_CAPACITY, build_net_demand

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")
DATA_DRY = os.path.join(os.path.dirname(__file__), "../data/Nordic_dry.xlsx")

PEAK_SCALE = 1.2   # demand multiplier for peak scenarios


def main():
    print("\n" + "=" * 72)
    print("  TASK 4-3  |  Supply Scarcity — Compound Scenarios")
    print("=" * 72)

    # Read base demands
    base_wet = dict(_read_excel(DATA_WET)["Nodes"]["DEMAND"])
    base_dry = dict(_read_excel(DATA_DRY)["Nodes"]["DEMAND"])

    peak_wet = {n: d * PEAK_SCALE for n, d in base_wet.items()}
    peak_dry = {n: d * PEAK_SCALE for n, d in base_dry.items()}

    net_wet      = build_net_demand(base_wet)
    net_dry      = build_net_demand(base_dry)
    net_peak_wet = build_net_demand(peak_wet)
    net_peak_dry = build_net_demand(peak_dry)

    scenarios = [
        ("S1", "Wet, no wind, base demand",       DATA_WET, True, None),
        ("S2", "Wet, full wind, base demand",      DATA_WET, True, net_wet),
        ("S3", f"Wet, full wind, demand×{PEAK_SCALE}",  DATA_WET, True, net_peak_wet),
        ("S4", "Dry, no wind, base demand",       DATA_DRY, True, None),
        ("S5", "Dry, full wind, base demand",      DATA_DRY, True, net_dry),
        ("S6", f"Dry, full wind, demand×{PEAK_SCALE}",  DATA_DRY, True, net_peak_dry),
    ]

    results = {}
    for sid, label, fname, dcflow, demand_ov in scenarios:
        print(f"\n>>> [{sid}] {label} ...")
        results[sid] = solve_nordic(fname, dcflow=dcflow, demand_override=demand_ov)
        cr_, total_cr = compute_congestion_rent(results[sid])
        shed = sum(results[sid]["shed"].values())
        print(f"    Cost: {results[sid]['objective']:,.0f} €/h  |  "
              f"CR: {total_cr:,.0f} €/h  |  Shed: {shed:.1f} MW")

    # ---------------------------------------------------------------- Table A.13
    names = results["S1"]["node_names"]
    print("\n\n" + "=" * 90)
    print("  Table A.13 — Supply Scarcity: Compound Scenario Comparison (FBMC)")
    print("=" * 90)

    # System-level summary
    print(f"\n  {'Scenario':<6} {'Description':<40} {'Cost [€/h]':>12} {'CR [€/h]':>10} {'Shed [MW]':>10}")
    print(f"  {'-'*6} {'-'*40} {'-'*12} {'-'*10} {'-'*10}")
    for sid, label, _, _, _ in scenarios:
        res = results[sid]
        _, total_cr = compute_congestion_rent(res)
        shed = sum(res["shed"].values())
        print(f"  {sid:<6} {label:<40} {res['objective']:>12,.0f} {total_cr:>10,.0f} {shed:>10.2f}")

    # Nodal prices across scenarios
    print(f"\n  Nodal Prices [€/MWh]:")
    print(f"  {'Node':<5} {'Name':<6}" + "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['prices'][n]:>8.2f}"
        print(row)

    # Generation across scenarios
    print(f"\n  Generation [MW]:")
    print(f"  {'Node':<5} {'Name':<6}" + "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['gen'][n]:>8.1f}"
        print(row)

    # Load shedding detail
    print(f"\n  Load Shedding [MW]:")
    print(f"  {'Node':<5} {'Name':<6}" + "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['shed'][n]:>8.2f}"
        print(row)

    # Key insights
    print("\n\n" + "=" * 72)
    print("  Key Observations")
    print("=" * 72)
    cost_s1 = results["S1"]["objective"]
    for sid, label, _, _, _ in scenarios[1:]:
        delta = results[sid]["objective"] - cost_s1
        print(f"  [{sid}] {label:<40} ΔCost vs S1: {delta:>+12,.0f} €/h")


if __name__ == "__main__":
    main()
