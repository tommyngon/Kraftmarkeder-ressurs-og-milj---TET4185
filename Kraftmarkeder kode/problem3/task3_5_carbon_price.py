"""
Task 3-5 — Carbon Price / EU ETS Sensitivity
=============================================
Adds a CO₂ price adder to each node's marginal generation cost:
    GENCOST_new[n] = GENCOST[n] + intensity[n] * p_CO2

Emission intensities are taken from Table A.8 in the report.
Three CO₂ price scenarios are modelled:
    p_CO2 ∈ {0, 25, 50, 75, 100}  €/tCO₂

Results are compared to the wet-year base case (no carbon price).

Reproduces:
  Table A.8  — Node emission intensities (shown in code / comments)
  Table A.9  — Generation & prices for each CO₂ price level (FBMC)
  Table A.10 — Congestion rent sensitivity to CO₂ price (FBMC)

Run
---
    cd code/
    python problem3/task3_5_carbon_price.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from nordic_base import solve_nordic, compute_congestion_rent

DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# -----------------------------------------------------------------------
# Table A.8 — Emission intensities [gCO₂/kWh = kgCO₂/MWh = tCO₂/GWh]
# Nodes:  1=NO4, 2=NO3, 3=NO5, 4=NO2, 5=NO1
#         6=SE1, 7=SE2, 8=SE3, 9=SE4, 10=FI, 11=DK1, 12=DK2
# -----------------------------------------------------------------------
EMISSION_INTENSITY = {   # [tCO₂/MWh]  (gCO₂/kWh ÷ 1000)
    1:  0.024,   # NO4  — hydro dominated
    2:  0.020,   # NO3
    3:  0.019,   # NO5
    4:  0.022,   # NO2
    5:  0.026,   # NO1
    6:  0.015,   # SE1  — nuclear/hydro
    7:  0.015,   # SE2
    8:  0.015,   # SE3
    9:  0.015,   # SE4
    10: 0.095,   # FI   — mixed (gas/nuclear)
    11: 0.155,   # DK1  — wind + coal/gas
    12: 0.120,   # DK2
}

# CO₂ price scenarios [€/tCO₂]
CO2_PRICES = [0, 25, 50, 75, 100]


def build_cost_override(base_data_costs, p_co2):
    """
    Compute cost override dict adding CO₂ adder to base marginal costs.
    We read base costs fresh from the data to ensure clean stacking.
    """
    override = {}
    for n, intensity in EMISSION_INTENSITY.items():
        override[n] = base_data_costs[n] + intensity * p_co2
    return override


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-5  |  Carbon Price Sensitivity  |  FBMC Wet Year")
    print("=" * 72)

    # Read base marginal costs from Excel (before any CO₂ adder)
    from nordic_base import _read_excel
    base_data = _read_excel(DATA_WET)
    base_gencost = dict(base_data["Nodes"]["GENCOST"])  # {n: €/MWh}

    results = {}
    for p_co2 in CO2_PRICES:
        print(f"\n>>> Solving FBMC with CO₂ price = {p_co2} €/tCO₂ ...")
        cost_ov = build_cost_override(base_gencost, p_co2)
        res = solve_nordic(DATA_WET, dcflow=True, cost_override=cost_ov)
        results[p_co2] = res

    # ---------------------------------------------------------------- Table A.9 — Prices
    names = results[0]["node_names"]
    print("\n\n" + "=" * 90)
    print("  Table A.9 — Nodal Prices [€/MWh] for each CO₂ price level  (FBMC, Wet Year)")
    print("=" * 90)
    header = f"  {'Node':<5} {'Name':<6}" + "".join(f" {'p=' + str(p) + '€':>10}" for p in CO2_PRICES)
    print(header)
    print("  " + "-" * (11 + 10 * len(CO2_PRICES)))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for p_co2 in CO2_PRICES:
            row += f" {results[p_co2]['prices'][n]:>10.2f}"
        print(row)

    # ---------------------------------------------------------------- Objective & CR
    print("\n\n" + "=" * 90)
    print("  Table A.10 — System Cost & Congestion Rent vs. CO₂ Price  (FBMC, Wet Year)")
    print("=" * 90)
    print(f"  {'CO₂ Price [€/t]':<18} {'Objective [€/h]':>16} {'Cong. Rent [€/h]':>18} "
          f"{'Shedding [MW]':>14}")
    print(f"  {'-'*18} {'-'*16} {'-'*18} {'-'*14}")
    for p_co2 in CO2_PRICES:
        res = results[p_co2]
        _, total_cr = compute_congestion_rent(res)
        print(f"  {p_co2:<18} {res['objective']:>16,.2f} {total_cr:>18,.2f} "
              f"{sum(res['shed'].values()):>14.2f}")

    # ---------------------------------------------------------------- Generation shift
    print("\n\n" + "=" * 90)
    print("  Generation Shift [MW] relative to p_CO2 = 0  (FBMC, Wet Year)")
    print("=" * 90)
    header = f"  {'Node':<5} {'Name':<6}" + "".join(f" {'Δ@' + str(p):>10}" for p in CO2_PRICES[1:])
    print(header)
    print("  " + "-" * (11 + 10 * (len(CO2_PRICES)-1)))
    gen_base = results[0]["gen"]
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for p_co2 in CO2_PRICES[1:]:
            delta = results[p_co2]["gen"][n] - gen_base[n]
            row += f" {delta:>+10.1f}"
        print(row)

    # ---------------------------------------------------------------- Effective costs
    print("\n\n" + "=" * 72)
    print("  Effective marginal costs at each CO₂ price level")
    print("=" * 72)
    print(f"  {'Node':<5} {'Name':<6} {'Intensity':>11}" +
          "".join(f" {'p=' + str(p):>9}" for p in CO2_PRICES))
    print("  " + "-" * (23 + 9 * len(CO2_PRICES)))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6} {EMISSION_INTENSITY[n]:>11.3f}"
        for p_co2 in CO2_PRICES:
            row += f" {base_gencost[n] + EMISSION_INTENSITY[n]*p_co2:>9.2f}"
        print(row)
    print("  (intensities in tCO₂/MWh, costs in €/MWh)")


if __name__ == "__main__":
    main()
