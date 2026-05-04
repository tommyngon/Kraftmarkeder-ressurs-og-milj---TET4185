"""
Task 4-1 — Wind Integration
============================
Models large-scale wind integration by reducing net demand at each node:
    D_net[n] = D[n] - W[n]

Wind capacities are taken from Table A.11 in the report.
The net demand is fed as a demand_override into the FBMC and ATC models
(wet year base case).

Reproduces:
  Table A.11 — Wind capacities [MW] per node and resulting generation/prices

Run
---
    cd code/
    python problem4/task4_1_wind_integration.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../problem3"))
from nordic_base import (
    solve_nordic, print_generation_table,
    print_congestion_table, compute_congestion_rent,
    _read_excel,
)

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# -----------------------------------------------------------------------
# Table A.11 — Wind capacities [MW]
# Nodes:  1=NO4, 2=NO3, 3=NO5, 4=NO2, 5=NO1
#         6=SE1, 7=SE2, 8=SE3, 9=SE4, 10=FI, 11=DK1, 12=DK2
# -----------------------------------------------------------------------
WIND_CAPACITY = {   # [MW]  full-load capacity (assumed fully dispatched)
    1:   500,   # NO4
    2:   800,   # NO3
    3:   500,   # NO5
    4:  1100,   # NO2
    5:  1300,   # NO1
    6:   400,   # SE1
    7:   600,   # SE2
    8:  4200,   # SE3
    9:  2000,   # SE4
    10: 2300,   # FI
    11: 3200,   # DK1
    12: 2200,   # DK2
}

TOTAL_WIND = sum(WIND_CAPACITY.values())


def build_net_demand(base_demand):
    """Subtract wind output from base demand to get net demand per node."""
    net = {}
    for n, d in base_demand.items():
        w = WIND_CAPACITY.get(n, 0)
        net[n] = max(0.0, d - w)   # net demand cannot go negative
    return net


def main():
    print("\n" + "=" * 72)
    print("  TASK 4-1  |  Wind Integration")
    print("=" * 72)
    print(f"  Total wind installed: {TOTAL_WIND:,} MW")

    # Read base demand
    base_data   = _read_excel(DATA_WET)
    base_demand = dict(base_data["Nodes"]["DEMAND"])
    net_demand  = build_net_demand(base_demand)

    # Print wind table
    names = base_data["Nodes"]["NNAMES"]
    print(f"\n  Table A.11 — Wind Integration: Demand Reduction per Node")
    print(f"  {'Node':<5} {'Name':<6} {'Base Demand':>12} {'Wind Cap':>10} "
          f"{'Net Demand':>11} {'Wind share':>11}")
    print(f"  {'-'*5} {'-'*6} {'-'*12} {'-'*10} {'-'*11} {'-'*11}")
    for n in sorted(base_demand):
        d  = base_demand[n]
        w  = WIND_CAPACITY.get(n, 0)
        dn = net_demand[n]
        share = w / d * 100 if d > 0 else 0
        print(f"  {n:<5} {names[n]:<6} {d:>12.0f} {w:>10.0f} {dn:>11.0f} {share:>10.1f}%")
    print(f"  {'':5} {'TOTAL':<6} {sum(base_demand.values()):>12.0f} "
          f"{TOTAL_WIND:>10.0f} {sum(net_demand.values()):>11.0f}")

    # ------------------------------------------------------------------ Solve
    print("\n>>> Solving FBMC — No wind (base) ...")
    res_base = solve_nordic(DATA_WET, dcflow=True)

    print("\n>>> Solving FBMC — With wind integration ...")
    res_wind = solve_nordic(DATA_WET, dcflow=True, demand_override=net_demand)

    print("\n>>> Solving ATC — With wind integration ...")
    res_wind_atc = solve_nordic(DATA_WET, dcflow=False, demand_override=net_demand)

    # ---------------------------------------------------------------- Print tables
    print_generation_table(res_base, title="Wet Year Base (FBMC, no wind)")
    print_generation_table(res_wind, title="Wind Integration (FBMC, net demand)")
    print_congestion_table(res_wind, title="Wind Integration — AC Flows & Congestion Rent (FBMC)")

    cr_base, total_cr_base = compute_congestion_rent(res_base)
    cr_wind, total_cr_wind = compute_congestion_rent(res_wind)
    cr_wind_atc, total_cr_wind_atc = compute_congestion_rent(res_wind_atc)

    # ---------------------------------------------------------------- Comparison
    print("\n\n" + "=" * 80)
    print("  Wind Integration: Before vs. After Comparison (FBMC)")
    print("=" * 80)
    print(f"  {'Node':<5} {'Name':<6} {'Gen Base':>9} {'Gen Wind':>9} {'ΔGen':>7} "
          f"{'π Base':>8} {'π Wind':>8} {'Δπ':>7}")
    print(f"  {'-'*5} {'-'*6} {'-'*9} {'-'*9} {'-'*7} {'-'*8} {'-'*8} {'-'*7}")
    for n in sorted(res_base["gen"]):
        gb  = res_base["gen"][n]
        gw  = res_wind["gen"][n]
        pb  = res_base["prices"][n]
        pw  = res_wind["prices"][n]
        print(f"  {n:<5} {names[n]:<6} {gb:>9.1f} {gw:>9.1f} {gw-gb:>+7.1f} "
              f"{pb:>8.2f} {pw:>8.2f} {pw-pb:>+7.2f}")

    print(f"\n  {'Metric':<45} {'Base':>12} {'Wind (FBMC)':>12} {'Wind (ATC)':>12}")
    print(f"  {'-'*45} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'System cost [€/h]':<45} "
          f"{res_base['objective']:>12,.2f} {res_wind['objective']:>12,.2f} "
          f"{res_wind_atc['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]':<45} "
          f"{total_cr_base:>12,.2f} {total_cr_wind:>12,.2f} "
          f"{total_cr_wind_atc:>12,.2f}")
    print(f"  {'Total thermal generation [MW]':<45} "
          f"{sum(res_base['gen'].values()):>12.1f} {sum(res_wind['gen'].values()):>12.1f} "
          f"{sum(res_wind_atc['gen'].values()):>12.1f}")
    print(f"  {'Load shedding [MW]':<45} "
          f"{sum(res_base['shed'].values()):>12.2f} {sum(res_wind['shed'].values()):>12.2f} "
          f"{sum(res_wind_atc['shed'].values()):>12.2f}")


if __name__ == "__main__":
    main()
