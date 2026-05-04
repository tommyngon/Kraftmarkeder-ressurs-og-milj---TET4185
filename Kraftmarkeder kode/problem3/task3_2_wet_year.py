"""
Task 3-2 — Wet Year: FBMC and ATC market clearing
===================================================
Solves the Nordic 12-node market for the wet year using both:
  - FBMC (DC power flow / PTDF-based DCOPF)
  - ATC  (Available Transfer Capacity / transport network)

Reproduces:
  Table A.1  — Generation and nodal prices (wet year, both methods)
  Table A.2  — AC line flows and congestion rent (wet year, both methods)

Run
---
    cd code/
    python problem3/task3_2_wet_year.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from nordic_base import solve_nordic, print_generation_table, print_congestion_table, compute_congestion_rent

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-2  |  Wet Year  |  FBMC vs ATC")
    print("=" * 72)

    # ------------------------------------------------------------------ FBMC
    print("\n>>> Solving FBMC (DC power flow) — Wet year ...")
    res_fbmc = solve_nordic(DATA_WET, dcflow=True)

    print_generation_table(res_fbmc, title="Table A.1 (partial) — Wet Year, FBMC | Generation & Nodal Prices")
    print_congestion_table(res_fbmc, title="Table A.2 (partial) — Wet Year, FBMC | AC Line Flows & Congestion Rent")

    cr_fbmc, total_cr_fbmc = compute_congestion_rent(res_fbmc)
    print(f"\n  FBMC Congestion Rent total: {total_cr_fbmc:,.2f} €/h")
    print(f"  FBMC Objective (total cost): {res_fbmc['objective']:,.2f} €/h")

    # ------------------------------------------------------------------- ATC
    print("\n>>> Solving ATC (transport network) — Wet year ...")
    res_atc = solve_nordic(DATA_WET, dcflow=False)

    print_generation_table(res_atc, title="Table A.1 (partial) — Wet Year, ATC | Generation & Nodal Prices")
    print_congestion_table(res_atc, title="Table A.2 (partial) — Wet Year, ATC | AC Line Flows & Congestion Rent")

    cr_atc, total_cr_atc = compute_congestion_rent(res_atc)
    print(f"\n  ATC Congestion Rent total: {total_cr_atc:,.2f} €/h")
    print(f"  ATC Objective (total cost): {res_atc['objective']:,.2f} €/h")

    # ---------------------------------------------------------------- Summary
    print("\n\n" + "=" * 72)
    print("  COMPARISON SUMMARY — Wet Year")
    print("=" * 72)
    print(f"  {'Metric':<35} {'FBMC':>12} {'ATC':>12}")
    print(f"  {'-'*35} {'-'*12} {'-'*12}")
    print(f"  {'Total system cost [€/h]':<35} {res_fbmc['objective']:>12,.2f} {res_atc['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]':<35} {total_cr_fbmc:>12,.2f} {total_cr_atc:>12,.2f}")
    print(f"  {'Total shedding [MW]':<35} {sum(res_fbmc['shed'].values()):>12.2f} {sum(res_atc['shed'].values()):>12.2f}")

    names = res_fbmc["node_names"]
    print(f"\n  {'Node':<5} {'Name':<6} {'Price FBMC':>12} {'Price ATC':>12}")
    print(f"  {'-'*5} {'-'*6} {'-'*12} {'-'*12}")
    for n in sorted(res_fbmc["prices"]):
        print(f"  {n:<5} {names[n]:<6} {res_fbmc['prices'][n]:>12.2f} {res_atc['prices'][n]:>12.2f}")


if __name__ == "__main__":
    main()
