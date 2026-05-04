"""
Task 3-4 — Nuclear Phase-Out in SE3
=====================================
Models the effect of removing nuclear capacity in SE3 (node 8).
  Base case:   GENCAP[SE3] = 12 400 MW
  Phase-out:   GENCAP[SE3] =  4 000 MW  (reduction of 8 400 MW)

This is applied on top of the wet-year base case (FBMC and ATC).

Reproduces:
  Table A.6  — Generation & prices: base vs. nuclear phase-out (FBMC)
  Table A.7  — AC line flows & congestion rent: base vs. nuclear phase-out (FBMC)

Run
---
    cd code/
    python problem3/task3_4_nuclear_phaseout.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from nordic_base import (
    solve_nordic, print_generation_table,
    print_congestion_table, compute_congestion_rent,
)

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# SE3 is node 8 in the Nordic 12-node system.
SE3_NODE = 8
SE3_BASE_CAP   = 12_400  # MW  (original full nuclear + thermal)
SE3_PHASEOUT_CAP = 4_000 # MW  (only remaining thermal, nuclear removed)


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-4  |  Nuclear Phase-Out (SE3: 12 400 → 4 000 MW)")
    print("=" * 72)

    # ------------------------------------------------------------------ Base
    print("\n>>> Solving BASE case (FBMC, wet year) ...")
    res_base = solve_nordic(DATA_WET, dcflow=True)

    print_generation_table(res_base, title="Table A.6 (left) — BASE | FBMC Wet Year")
    print_congestion_table(res_base, title="Table A.7 (left) — BASE | AC Flows & Congestion Rent")
    cr_base, total_cr_base = compute_congestion_rent(res_base)

    # -------------------------------------------------- Nuclear phase-out
    print(f"\n>>> Solving NUCLEAR PHASE-OUT (SE3 cap: {SE3_BASE_CAP} → {SE3_PHASEOUT_CAP} MW, FBMC) ...")
    res_phaseout = solve_nordic(
        DATA_WET,
        dcflow=True,
        gencap_override={SE3_NODE: SE3_PHASEOUT_CAP},
    )

    print_generation_table(res_phaseout, title="Table A.6 (right) — NUCLEAR PHASE-OUT | FBMC Wet Year")
    print_congestion_table(res_phaseout, title="Table A.7 (right) — NUCLEAR PHASE-OUT | AC Flows & Congestion Rent")
    cr_po, total_cr_po = compute_congestion_rent(res_phaseout)

    # ---------------------------------------------------------------- ATC versions
    print("\n>>> Solving BASE case (ATC, wet year) ...")
    res_base_atc = solve_nordic(DATA_WET, dcflow=False)
    cr_base_atc, total_cr_base_atc = compute_congestion_rent(res_base_atc)

    print(f"\n>>> Solving NUCLEAR PHASE-OUT (SE3 cap: {SE3_PHASEOUT_CAP} MW, ATC) ...")
    res_po_atc = solve_nordic(
        DATA_WET,
        dcflow=False,
        gencap_override={SE3_NODE: SE3_PHASEOUT_CAP},
    )
    cr_po_atc, total_cr_po_atc = compute_congestion_rent(res_po_atc)

    # ---------------------------------------------------------------- Comparison table
    names = res_base["node_names"]
    print("\n\n" + "=" * 80)
    print("  Table A.6 — Nuclear Phase-Out: Generation & Price Comparison")
    print("=" * 80)
    print(f"  {'Node':<5} {'Name':<6} {'Gen Base':>9} {'Gen PO':>9} {'ΔGen':>7} "
          f"{'π Base':>8} {'π PO':>8} {'Δπ':>7}")
    print(f"  {'-'*5} {'-'*6} {'-'*9} {'-'*9} {'-'*7} {'-'*8} {'-'*8} {'-'*7}")
    for n in sorted(res_base["gen"]):
        gb  = res_base["gen"][n]
        gpo = res_phaseout["gen"][n]
        pb  = res_base["prices"][n]
        ppo = res_phaseout["prices"][n]
        print(f"  {n:<5} {names[n]:<6} {gb:>9.1f} {gpo:>9.1f} {gpo-gb:>+7.1f} "
              f"{pb:>8.2f} {ppo:>8.2f} {ppo-pb:>+7.2f}")

    print(f"\n  {'Metric':<45} {'Base':>12} {'Phase-Out':>12}")
    print(f"  {'-'*45} {'-'*12} {'-'*12}")
    print(f"  {'System cost [€/h]  (FBMC)':<45} {res_base['objective']:>12,.2f} {res_phaseout['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]  (FBMC)':<45} {total_cr_base:>12,.2f} {total_cr_po:>12,.2f}")
    print(f"  {'Total shedding [MW]  (FBMC)':<45} {sum(res_base['shed'].values()):>12.2f} {sum(res_phaseout['shed'].values()):>12.2f}")
    print(f"  {'System cost [€/h]  (ATC)':<45} {res_base_atc['objective']:>12,.2f} {res_po_atc['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]  (ATC)':<45} {total_cr_base_atc:>12,.2f} {total_cr_po_atc:>12,.2f}")


if __name__ == "__main__":
    main()
