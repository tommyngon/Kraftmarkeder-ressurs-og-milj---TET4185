"""
Task 3-5 — Carbon Price / EU ETS Sensitivity

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
  fig_35c_co2_cost.pdf/.png    — Stacked bar: base cost + CO₂ adder per zone
  fig_35e_co2_results.pdf/.png — Side-by-side: generation and prices, base vs 65 €/t

Run

    cd code/
    python problem3/task3_5_carbon_price.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from nordic_base import solve_nordic, compute_congestion_rent

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")


# Table A.8 — Emission intensities [tCO₂/MWh]  (= gCO₂/kWh ÷ 1000)
# Nodes:  1=NO4, 2=NO3, 3=NO5, 4=NO2, 5=NO1
#         6=SE1, 7=SE2, 8=SE3, 9=SE4, 10=FI, 11=DK1, 12=DK2

EMISSION_INTENSITY = {
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

# Reference price for fig_35c and fig_35e
CO2_REF = 65   # €/tCO₂  (today's approximate ETS price)

# Plot style 
C_BASE  = '#2166AC'   # steel blue  — base / original cost
C_CO2   = '#D6604D'   # muted red   — CO₂ adder / CO₂ scenario
C_DEM   = '#333333'
C_MC    = '#B2182B'

plt.rcParams.update({
    'font.family':      'sans-serif',
    'font.size':        10,
    'axes.titlesize':   12,
    'axes.titleweight': 'bold',
    'axes.labelsize':   11,
    'xtick.labelsize':   9,
    'ytick.labelsize':   9,
    'legend.fontsize':   9,
    'figure.dpi':       200,
})



# helpers

def _savefig(fig, stem):
    for ext in ('pdf', 'png'):
        path = os.path.join(OUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, bbox_inches='tight')
        print(f"  Saved: {path}")
    plt.close(fig)


def _node_list(res):
    names = res['node_names']
    nodes_sorted = sorted(names.keys())
    labels = [names[n] for n in nodes_sorted]
    return nodes_sorted, labels


def _country_bands(ax, n_nodes=12):
    bands = [(-0.5, 4.5, 'blue'), (4.5, 8.5, 'orange'),
             (8.5, 9.5, 'green'), (9.5, n_nodes - 0.5, 'red')]
    for x0, x1, c in bands:
        ax.axvspan(x0, x1, alpha=0.04, color=c)


def build_cost_override(base_gencost, p_co2):
    """Return cost override dict: base cost + CO₂ adder for every node."""
    return {n: base_gencost[n] + EMISSION_INTENSITY[n] * p_co2
            for n in EMISSION_INTENSITY}



# FIGURE C — Stacked bar: original cost + CO₂ adder at CO2_REF price


def fig_co2_cost(res_base, base_gencost):
    """
    Stacked bar chart showing, for each zone:
      - Original marginal cost (blue)
      - CO₂ adder at CO2_REF €/tCO₂ (red, stacked on top)
    Annotates each red segment with the adder value in €/MWh.
    Data comes from base_gencost dict + EMISSION_INTENSITY constant.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    orig_cost = [base_gencost[n]                           for n in nodes_sorted]
    co2_adder = [EMISSION_INTENSITY[n] * CO2_REF           for n in nodes_sorted]

    fig, ax = plt.subplots(figsize=(12, 5.0))
    bw = 0.55

    ax.bar(idx, orig_cost, bw,
           label='Original marginal cost', color=C_BASE,
           edgecolor='white', linewidth=.6)
    ax.bar(idx, co2_adder, bw, bottom=orig_cost,
           label=f'CO₂ cost adder ({CO2_REF} €/tCO₂)', color=C_CO2,
           edgecolor='white', linewidth=.6)

    # Annotate adder value above each red segment
    for i, (base, adder) in enumerate(zip(orig_cost, co2_adder)):
        ax.text(i, base + adder + 1.5, f'+{adder:.1f}',
                ha='center', va='bottom', fontsize=8,
                color=C_CO2, fontweight='bold')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Marginal cost (€/MWh)')
    ax.set_title(f'Effect of {CO2_REF} €/tCO₂ Carbon Price on Zonal Generation Costs')
    ax.set_ylim(0, max(o + a for o, a in zip(orig_cost, co2_adder)) * 1.20)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    fig.tight_layout()
    _savefig(fig, 'fig_35c_co2_cost')


# FIGURE E — Side-by-side: generation and prices, base vs CO2_REF scenario
# ══════════════════════════════════════════════════════════════════════════════

def fig_co2_results(res_base, res_co2ref):
    """
    Side-by-side bar charts:
      Left  — generation dispatch: base (blue) vs CO₂_REF scenario (red).
               Demand shown as dashed step line.
      Right — zonal prices: base (blue) vs CO₂_REF (red).
               Effective marginal costs (CO₂-adjusted) shown as diamonds.
    Data pulled entirely from live solver result dicts.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    base_gen    = [res_base['gen'].get(n, 0)      for n in nodes_sorted]
    co2_gen     = [res_co2ref['gen'].get(n, 0)    for n in nodes_sorted]
    demand      = [res_base['demand'].get(n, 0)   for n in nodes_sorted]
    base_price  = [res_base['prices'].get(n, 0)   for n in nodes_sorted]
    co2_price   = [res_co2ref['prices'].get(n, 0) for n in nodes_sorted]
    # Effective marginal cost (CO₂-adjusted) for the diamond overlay
    eff_cost    = [res_co2ref['gencost'].get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})
    bw = 0.34

    # Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in base_gen], bw,
           label='Base (no CO₂)', color=C_BASE, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [g/1e3 for g in co2_gen], bw,
           label=f'{CO2_REF} €/tCO₂', color=C_CO2, edgecolor='white', linewidth=.6)

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand] + [demand[-1]/1e3],
            where='post', color=C_DEM, lw=1.4, ls='--', label='Demand')

    # Annotate the DK swap (DK1 shrinks, DK2 grows — high CO₂ intensity)
    for i, n in enumerate(nodes_sorted):
        delta_g = co2_gen[i] - base_gen[i]
        if abs(delta_g) > 500:
            y = max(base_gen[i], co2_gen[i]) / 1e3 + 0.15
            ax.text(i, y, f'{delta_g/1e3:+.1f}',
                    ha='center', va='bottom', fontsize=8,
                    color=C_CO2 if delta_g > 0 else C_BASE)

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title(f'Generation Dispatch — Base vs. {CO2_REF} €/tCO₂')
    ax.legend(loc='upper right', fontsize=8)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    # Right: prices 
    ax = axes[1]
    ax.bar(idx - bw/2, base_price, bw,
           label='Base (no CO₂)', color=C_BASE, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, co2_price, bw,
           label=f'{CO2_REF} €/tCO₂', color=C_CO2, edgecolor='white', linewidth=.6)
    ax.plot(idx, eff_cost, 'D', color=C_MC, ms=6, zorder=5,
            label='Eff. marginal cost (CO₂-adj.)')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh)')
    ax.set_title(f'Zonal Prices — Base vs. {CO2_REF} €/tCO₂')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    _savefig(fig, 'fig_35e_co2_results')



# Main


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-5  |  Carbon Price Sensitivity  |  FBMC Wet Year")
    print("=" * 72)

    # Read base marginal costs from Excel (before any CO₂ adder)
    from nordic_base import _read_excel
    base_data    = _read_excel(DATA_WET)
    base_gencost = dict(base_data["Nodes"]["GENCOST"])   # {n: €/MWh}

    # Solve all scenarios
    results = {}
    for p_co2 in CO2_PRICES:
        print(f"\n>>> Solving FBMC with CO₂ price = {p_co2} €/tCO₂ ...")
        cost_ov = build_cost_override(base_gencost, p_co2)
        results[p_co2] = solve_nordic(DATA_WET, dcflow=True,
                                      cost_override=cost_ov)

    # Also solve the reference CO₂ scenario (65 €/t) for the figures
    print(f"\n>>> Solving FBMC with CO₂ price = {CO2_REF} €/tCO₂ (reference for figures) ...")
    cost_ref    = build_cost_override(base_gencost, CO2_REF)
    res_co2ref  = solve_nordic(DATA_WET, dcflow=True, cost_override=cost_ref)
    res_base    = results[0]

    # Table A.9 — Prices
    names = results[0]["node_names"]
    print("\n\n" + "=" * 90)
    print("  Table A.9 — Nodal Prices [€/MWh] for each CO₂ price level  (FBMC, Wet Year)")
    print("=" * 90)
    header = f"  {'Node':<5} {'Name':<6}" + \
             "".join(f" {'p='+str(p)+'€':>10}" for p in CO2_PRICES)
    print(header)
    print("  " + "-" * (11 + 10 * len(CO2_PRICES)))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for p_co2 in CO2_PRICES:
            row += f" {results[p_co2]['prices'][n]:>10.2f}"
        print(row)

    # Objective & CR
    print("\n\n" + "=" * 90)
    print("  Table A.10 — System Cost & Congestion Rent vs. CO₂ Price  (FBMC, Wet Year)")
    print("=" * 90)
    print(f"  {'CO₂ Price [€/t]':<18} {'Objective [€/h]':>16} "
          f"{'Cong. Rent [€/h]':>18} {'Shedding [MW]':>14}")
    print(f"  {'-'*18} {'-'*16} {'-'*18} {'-'*14}")
    for p_co2 in CO2_PRICES:
        res = results[p_co2]
        _, total_cr = compute_congestion_rent(res)
        print(f"  {p_co2:<18} {res['objective']:>16,.2f} {total_cr:>18,.2f} "
              f"{sum(res['shed'].values()):>14.2f}")

    # Generation shift
    print("\n\n" + "=" * 90)
    print("  Generation Shift [MW] relative to p_CO2 = 0  (FBMC, Wet Year)")
    print("=" * 90)
    header = f"  {'Node':<5} {'Name':<6}" + \
             "".join(f" {'Δ@'+str(p):>10}" for p in CO2_PRICES[1:])
    print(header)
    print("  " + "-" * (11 + 10 * (len(CO2_PRICES) - 1)))
    gen_base = results[0]["gen"]
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for p_co2 in CO2_PRICES[1:]:
            delta = results[p_co2]["gen"][n] - gen_base[n]
            row += f" {delta:>+10.1f}"
        print(row)

    # Effective costs
    print("\n\n" + "=" * 72)
    print("  Effective marginal costs at each CO₂ price level")
    print("=" * 72)
    print(f"  {'Node':<5} {'Name':<6} {'Intensity':>11}" +
          "".join(f" {'p='+str(p):>9}" for p in CO2_PRICES))
    print("  " + "-" * (23 + 9 * len(CO2_PRICES)))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6} {EMISSION_INTENSITY[n]:>11.3f}"
        for p_co2 in CO2_PRICES:
            row += f" {base_gencost[n] + EMISSION_INTENSITY[n]*p_co2:>9.2f}"
        print(row)
    print("  (intensities in tCO₂/MWh, costs in €/MWh)")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_co2_cost(res_base, base_gencost)
    fig_co2_results(res_base, res_co2ref)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
