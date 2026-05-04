"""
Task 4-1 — Wind Integration

Models large-scale wind integration by reducing net demand at each node:
    D_net[n] = D[n] - W[n]

Wind capacities are taken from Table A.11 in the report.
The net demand is fed as a demand_override into the FBMC and ATC models
(wet year base case).

Reproduces:
  Table A.11 — Wind capacities [MW] per node and resulting generation/prices
  fig_41_wind_gen_prices.pdf/.png — Generation dispatch + prices (base vs wind)
  fig_41_wind_ac_flows.pdf/.png   — AC line flows (base vs wind)

Run

    cd code/
    python problem4/task4_1_wind_integration.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../problem3"))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from nordic_base import (
    solve_nordic,
    print_generation_table,
    print_congestion_table,
    compute_congestion_rent,
    _read_excel,
)

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")


# Table A.11 — Wind capacities [MW]
# Nodes:  1=NO4, 2=NO3, 3=NO5, 4=NO2, 5=NO1
#         6=SE1, 7=SE2, 8=SE3, 9=SE4, 10=FI, 11=DK1, 12=DK2

WIND_CAPACITY = {
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

# Plot style 
C_BASE     = '#2166AC'   # steel blue  — base case
C_WIND_GEN = '#4DAF4A'   # green       — conventional gen in wind case
C_WIND_BAR = '#A6D854'   # light green — wind generation stacked bar
C_DEM      = '#333333'
C_CAP_FWD  = '#B2182B'
C_CAP_REV  = '#67001F'

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


def build_net_demand(base_demand):
    """Subtract wind output from base demand to get net demand per node."""
    return {n: max(0.0, d - WIND_CAPACITY.get(n, 0))
            for n, d in base_demand.items()}



# FIGURE 1 — Generation dispatch + prices  (base vs wind)


def fig_wind_gen_prices(res_base, res_wind, base_demand):
    """
    Left:  Generation bars.
             Base case:  single blue bar (conventional only).
             Wind case:  green bar (conventional) with light-green hatched
                         wind segment stacked on top up to full demand.
           Demand shown as dashed step line.
    Right: Zonal prices — base (blue) vs wind (green).
    Data pulled entirely from live solver result dicts.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    base_gen   = [res_base['gen'].get(n, 0)   for n in nodes_sorted]
    wind_gen   = [res_wind['gen'].get(n, 0)   for n in nodes_sorted]
    wind_w     = [WIND_CAPACITY.get(n, 0)     for n in nodes_sorted]
    demand     = [base_demand.get(n, 0)       for n in nodes_sorted]
    base_price = [res_base['prices'].get(n, 0) for n in nodes_sorted]
    wind_price = [res_wind['prices'].get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})
    bw = 0.34

    # Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in base_gen], bw,
           label='Base (conventional)', color=C_BASE,
           edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [g/1e3 for g in wind_gen], bw,
           label='Wind case (conventional)', color=C_WIND_GEN,
           edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [w/1e3 for w in wind_w], bw,
           bottom=[g/1e3 for g in wind_gen],
           label='Wind generation', color=C_WIND_BAR,
           edgecolor='white', linewidth=.6, hatch='///')

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand] + [demand[-1]/1e3],
            where='post', color=C_DEM, lw=1.4, ls='--', label='Demand')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — Base vs. Wind Integration (FBMC)')
    ax.legend(loc='upper right', fontsize=8)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    # Right: prices 
    ax = axes[1]
    ax.bar(idx - bw/2, base_price, bw,
           label='Base', color=C_BASE, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, wind_price, bw,
           label='With wind', color=C_WIND_GEN, edgecolor='white', linewidth=.6)

    # Annotate price drop where wind is significant (>10 €/MWh change)
    for i, n in enumerate(nodes_sorted):
        delta = wind_price[i] - base_price[i]
        if abs(delta) > 10:
            ypos = max(base_price[i], wind_price[i]) + 1.5
            ax.text(i, ypos, f'{delta:+.0f}', ha='center', va='bottom',
                    fontsize=8, color=C_WIND_GEN if delta < 0 else C_BASE)

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh)')
    ax.set_title('Zonal Prices — Base vs. Wind Integration (FBMC)')
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    _savefig(fig, 'fig_41_wind_gen_prices')



# FIGURE 2 — AC line flows  (base vs wind)
# ══════════════════════════════════════════════════════════════════════════════

def fig_wind_ac_flows(res_base, res_wind):
    """
    Horizontal bar chart of AC line flows — base (blue) vs wind (green).
    Forward capacity shown as dashed red line; reverse capacity as dotted dark-red.
    Data pulled directly from solver result dicts.
    Expects:
      res['ac_flows']  dict  line_label -> MW  (signed, from→to positive)
      res['ac_caps']   dict  line_label -> (cap_fwd, cap_rev)
    """
    ac_lines  = sorted(res_base['ac_flows'].keys())
    n         = len(ac_lines)
    idy       = np.arange(n)
    bw2       = 0.35

    base_vals = [res_base['ac_flows'][l] for l in ac_lines]
    wind_vals = [res_wind['ac_flows'][l]  for l in ac_lines]
    caps_pos  = [ res_base['ac_caps'][l][0] for l in ac_lines]
    caps_neg  = [-res_base['ac_caps'][l][1] for l in ac_lines]

    fig, ax = plt.subplots(figsize=(15, max(6, n * 0.55)))
    ax.barh(idy + bw2/2, base_vals, bw2,
            label='Base', color=C_BASE, edgecolor='white', linewidth=.5)
    ax.barh(idy - bw2/2, wind_vals, bw2,
            label='With wind', color=C_WIND_GEN, edgecolor='white', linewidth=.5)

    for i, (cp, cn) in enumerate(zip(caps_pos, caps_neg)):
        ax.plot([cp, cp], [i - 0.5, i + 0.5],
                color=C_CAP_FWD, lw=1.3, ls='--',
                label='Cap (fwd)' if i == 0 else '')
        ax.plot([cn, cn], [i - 0.5, i + 0.5],
                color=C_CAP_REV, lw=1.3, ls=':',
                label='Cap (rev)' if i == 0 else '')

    # Annotate lines where wind causes a direction reversal
    for i, (bv, wv) in enumerate(zip(base_vals, wind_vals)):
        if (bv > 50 and wv < -50) or (bv < -50 and wv > 50):
            ax.text(max(abs(wv), abs(bv)) * 0.05, i,
                    '⟵ reversal', va='center', fontsize=8,
                    color='#444444', style='italic')

    ax.axvline(0, color='black', lw=0.8)
    ax.set_yticks(idy)
    ax.set_yticklabels(ac_lines, fontsize=9)
    ax.set_xlabel('Flow (MW)')
    ax.set_title('AC Line Flows — Base vs. Wind Integration (FBMC)')
    ax.legend(loc='lower right', ncol=2)
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()

    _savefig(fig, 'fig_41_wind_ac_flows')



# MAIN


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
        d     = base_demand[n]
        w     = WIND_CAPACITY.get(n, 0)
        dn    = net_demand[n]
        share = w / d * 100 if d > 0 else 0
        print(f"  {n:<5} {names[n]:<6} {d:>12.0f} {w:>10.0f} "
              f"{dn:>11.0f} {share:>10.1f}%")
    print(f"  {'':5} {'TOTAL':<6} {sum(base_demand.values()):>12.0f} "
          f"{TOTAL_WIND:>10.0f} {sum(net_demand.values()):>11.0f}")

    # Solve
    print("\n>>> Solving FBMC — No wind (base) ...")
    res_base = solve_nordic(DATA_WET, dcflow=True)

    print("\n>>> Solving FBMC — With wind integration ...")
    res_wind = solve_nordic(DATA_WET, dcflow=True, demand_override=net_demand)

    print("\n>>> Solving ATC — With wind integration ...")
    res_wind_atc = solve_nordic(DATA_WET, dcflow=False, demand_override=net_demand)

    # Print tables
    print_generation_table(res_base,
        title="Wet Year Base (FBMC, no wind)")
    print_generation_table(res_wind,
        title="Wind Integration (FBMC, net demand)")
    print_congestion_table(res_wind,
        title="Wind Integration — AC Flows & Congestion Rent (FBMC)")

    cr_base,     total_cr_base     = compute_congestion_rent(res_base)
    cr_wind,     total_cr_wind     = compute_congestion_rent(res_wind)
    cr_wind_atc, total_cr_wind_atc = compute_congestion_rent(res_wind_atc)

    # Comparison
    print("\n\n" + "=" * 80)
    print("  Wind Integration: Before vs. After Comparison (FBMC)")
    print("=" * 80)
    print(f"  {'Node':<5} {'Name':<6} {'Gen Base':>9} {'Gen Wind':>9} {'ΔGen':>7} "
          f"{'π Base':>8} {'π Wind':>8} {'Δπ':>7}")
    print(f"  {'-'*5} {'-'*6} {'-'*9} {'-'*9} {'-'*7} {'-'*8} {'-'*8} {'-'*7}")
    for n in sorted(res_base["gen"]):
        gb = res_base["gen"][n]
        gw = res_wind["gen"][n]
        pb = res_base["prices"][n]
        pw = res_wind["prices"][n]
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
          f"{sum(res_base['gen'].values()):>12.1f} "
          f"{sum(res_wind['gen'].values()):>12.1f} "
          f"{sum(res_wind_atc['gen'].values()):>12.1f}")
    print(f"  {'Load shedding [MW]':<45} "
          f"{sum(res_base['shed'].values()):>12.2f} "
          f"{sum(res_wind['shed'].values()):>12.2f} "
          f"{sum(res_wind_atc['shed'].values()):>12.2f}")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_wind_gen_prices(res_base, res_wind, base_demand)
    fig_wind_ac_flows(res_base, res_wind)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
