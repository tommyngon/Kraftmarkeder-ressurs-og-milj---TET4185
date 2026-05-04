"""
Task 3-3 — Dry Year: FBMC and ATC market clearing
===================================================
Solves the Nordic 12-node market for the dry year using both FBMC and ATC.
The dry year Excel file has reduced hydro generation capacities throughout
the Nordic system.

Reproduces:
  Table A.3  — Generation and nodal prices (dry year, both methods)
  Table A.4  — AC line flows and congestion rent (dry year, both methods)
  Table A.5  — Wet vs. Dry year comparison

Run
---
    cd code/
    python problem3/task3_3_dry_year.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from nordic_base import solve_nordic, print_generation_table, print_congestion_table, compute_congestion_rent

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")
DATA_DRY = os.path.join(os.path.dirname(__file__), "../data/Nordic_dry.xlsx")


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-3  |  Dry Year  |  FBMC vs ATC")
    print("=" * 72)

    # ------------------------------------------------------------------ FBMC
    print("\n>>> Solving FBMC (DC power flow) — Dry year ...")
    res_fbmc = solve_nordic(DATA_DRY, dcflow=True)

    print_generation_table(res_fbmc, title="Table A.3 (partial) — Dry Year, FBMC | Generation & Nodal Prices")
    print_congestion_table(res_fbmc, title="Table A.4 (partial) — Dry Year, FBMC | AC Line Flows & Congestion Rent")

    cr_fbmc, total_cr_fbmc = compute_congestion_rent(res_fbmc)

    # ------------------------------------------------------------------- ATC
    print("\n>>> Solving ATC (transport network) — Dry year ...")
    res_atc = solve_nordic(DATA_DRY, dcflow=False)

    print_generation_table(res_atc, title="Table A.3 (partial) — Dry Year, ATC | Generation & Nodal Prices")
    print_congestion_table(res_atc, title="Table A.4 (partial) — Dry Year, ATC | AC Line Flows & Congestion Rent")

    cr_atc, total_cr_atc = compute_congestion_rent(res_atc)

    # ------------------------------------------------------------------ Wet year baseline
    print("\n>>> Solving FBMC — Wet year (for comparison) ...")
    res_wet_fbmc = solve_nordic(DATA_WET, dcflow=True)
    res_wet_atc  = solve_nordic(DATA_WET, dcflow=False)
    cr_wet_fbmc, total_cr_wet_fbmc = compute_congestion_rent(res_wet_fbmc)
    cr_wet_atc,  total_cr_wet_atc  = compute_congestion_rent(res_wet_atc)

    # ---------------------------------------------------------------- Summary (Table A.5)
    print("\n\n" + "=" * 80)
    print("  Table A.5 — Wet vs. Dry Year Comparison")
    print("=" * 80)
    print(f"  {'Metric':<40} {'Wet FBMC':>10} {'Dry FBMC':>10} {'Wet ATC':>10} {'Dry ATC':>10}")
    print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'System cost [€/h]':<40} "
          f"{res_wet_fbmc['objective']:>10,.0f} {res_fbmc['objective']:>10,.0f} "
          f"{res_wet_atc['objective']:>10,.0f} {res_atc['objective']:>10,.0f}")
    print(f"  {'Total congestion rent [€/h]':<40} "
          f"{total_cr_wet_fbmc:>10,.0f} {total_cr_fbmc:>10,.0f} "
          f"{total_cr_wet_atc:>10,.0f} {total_cr_atc:>10,.0f}")
    print(f"  {'Total load shedding [MW]':<40} "
          f"{sum(res_wet_fbmc['shed'].values()):>10.2f} {sum(res_fbmc['shed'].values()):>10.2f} "
          f"{sum(res_wet_atc['shed'].values()):>10.2f} {sum(res_atc['shed'].values()):>10.2f}")

    names = res_fbmc["node_names"]
    print(f"\n  Nodal prices (FBMC):")
    print(f"  {'Node':<5} {'Name':<6} {'Wet':>8} {'Dry':>8} {'Δ':>8}")
    print(f"  {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for n in sorted(res_fbmc["prices"]):
        pw = res_wet_fbmc["prices"][n]
        pd_ = res_fbmc["prices"][n]
        print(f"  {n:<5} {names[n]:<6} {pw:>8.2f} {pd_:>8.2f} {pd_-pw:>+8.2f}")


if __name__ == "__main__":
    main()
