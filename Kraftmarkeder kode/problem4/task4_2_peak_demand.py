"""
Task 4-2 — Peak Demand Scenarios
==================================
Scales total system demand using a multiplier to simulate high-demand (peak)
conditions. The demand is scaled proportionally across all nodes:
    D_scaled[n] = scale_factor * D_base[n]

Scenarios: scale_factor ∈ {0.8, 0.9, 1.0, 1.1, 1.2, 1.3}

Run on both FBMC and ATC (wet year base).

Reproduces:
  Table A.12 — System cost, prices, congestion rent vs. demand level

Run
---
    cd code/
    python problem4/task4_2_peak_demand.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../problem3"))
from nordic_base import (
    solve_nordic, print_generation_table, compute_congestion_rent, _read_excel,
)

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# Demand scale factors to test
DEMAND_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]


def scale_demand(base_demand, factor):
    """Return demand dict with all values scaled by factor."""
    return {n: d * factor for n, d in base_demand.items()}


def main():
    print("\n" + "=" * 72)
    print("  TASK 4-2  |  Peak Demand Scenarios  |  FBMC & ATC, Wet Year")
    print("=" * 72)

    base_data   = _read_excel(DATA_WET)
    base_demand = dict(base_data["Nodes"]["DEMAND"])
    base_total  = sum(base_demand.values())
    names       = base_data["Nodes"]["NNAMES"]

    results_fbmc = {}
    results_atc  = {}

    for scale in DEMAND_SCALES:
        demand_ov = scale_demand(base_demand, scale)
        total     = sum(demand_ov.values())
        print(f"\n>>> Solving FBMC — demand scale {scale:.1f}x  (total = {total:,.0f} MW) ...")
        results_fbmc[scale] = solve_nordic(DATA_WET, dcflow=True,  demand_override=demand_ov)
        print(f">>> Solving ATC  — demand scale {scale:.1f}x ...")
        results_atc[scale]  = solve_nordic(DATA_WET, dcflow=False, demand_override=demand_ov)

    # ---------------------------------------------------------------- Table A.12
    print("\n\n" + "=" * 100)
    print("  Table A.12 — Peak Demand Sensitivity: FBMC Results")
    print("=" * 100)
    print(f"  {'Scale':<7} {'Total D [MW]':>13} {'Cost [€/h]':>13} {'CR [€/h]':>11} "
          f"{'Shed [MW]':>10}" + "".join(f" {'π' + names[n]:>8}" for n in sorted(names)))
    print("  " + "-" * (44 + 8*len(names)))

    for scale in DEMAND_SCALES:
        res = results_fbmc[scale]
        total_d = sum(scale_demand(base_demand, scale).values())
        _, total_cr = compute_congestion_rent(res)
        row = (f"  {scale:<7.1f} {total_d:>13,.0f} {res['objective']:>13,.0f} "
               f"{total_cr:>11,.0f} {sum(res['shed'].values()):>10.2f}")
        for n in sorted(names):
            row += f" {res['prices'][n]:>8.2f}"
        print(row)

    print(f"\n\n  {'Scale':<7} {'Total D [MW]':>13} {'Cost [€/h]':>13} {'CR [€/h]':>11} "
          f"{'Shed [MW]':>10}" + "".join(f" {'π' + names[n]:>8}" for n in sorted(names)))
    print("  ATC Results:")
    print("  " + "-" * (44 + 8*len(names)))
    for scale in DEMAND_SCALES:
        res = results_atc[scale]
        total_d = sum(scale_demand(base_demand, scale).values())
        _, total_cr = compute_congestion_rent(res)
        row = (f"  {scale:<7.1f} {total_d:>13,.0f} {res['objective']:>13,.0f} "
               f"{total_cr:>11,.0f} {sum(res['shed'].values()):>10.2f}")
        for n in sorted(names):
            row += f" {res['prices'][n]:>8.2f}"
        print(row)

    # ---------------------------------------------------------------- Print detailed for 1.0x and 1.2x
    for scale in [1.0, 1.2]:
        res = results_fbmc[scale]
        print_generation_table(res, title=f"FBMC — Demand scale {scale:.1f}x")

    # ---------------------------------------------------------------- Price range summary
    print("\n\n" + "=" * 72)
    print("  Price Range Summary (FBMC): min and max nodal prices per scenario")
    print("=" * 72)
    print(f"  {'Scale':<7} {'Min Price':>10} {'Max Price':>10} {'Spread':>10} {'Shed [MW]':>10}")
    print(f"  {'-'*7} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for scale in DEMAND_SCALES:
        prices = list(results_fbmc[scale]["prices"].values())
        shed   = sum(results_fbmc[scale]["shed"].values())
        print(f"  {scale:<7.1f} {min(prices):>10.2f} {max(prices):>10.2f} "
              f"{max(prices)-min(prices):>10.2f} {shed:>10.2f}")


if __name__ == "__main__":
    main()
