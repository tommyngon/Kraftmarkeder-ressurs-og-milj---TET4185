"""
Task 4-3 — Supply Scarcity: Wind Reduction + Compound Scenarios

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
  fig_43_scarcity.pdf/.png  — Prices + generation across wind-availability scenarios
  fig_43_compound.pdf/.png  — Compound scarcity: generation + shedding comparison

Run

    cd code/
    python problem4/task4_3_supply_scarcity.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../problem3"))
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import numpy as np

from nordic_base import solve_nordic, compute_congestion_rent, _read_excel
from task4_1_wind_integration import WIND_CAPACITY, build_net_demand

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")
DATA_DRY = os.path.join(os.path.dirname(__file__), "../data/Nordic_dry.xlsx")

PEAK_SCALE = 1.2   # demand multiplier for peak scenarios
CSHED      = 3_200  # €/MWh — shedding penalty (must match nordic_base)
PRICE_CAP  = 200    # €/MWh — display cap for price panels

# Plot style 
# Scenario colours
C_S1 = '#2166AC'   # blue   — S1 wet no-wind (reference)
C_S2 = '#4DAF4A'   # green  — S2 wet full-wind
C_S3 = '#FF7F00'   # orange — S3 wet full-wind peak demand
C_S4 = '#984EA3'   # purple — S4 dry no-wind
C_S5 = '#A65628'   # brown  — S5 dry full-wind
C_S6 = '#E41A1C'   # red    — S6 dry full-wind peak demand (worst case)

SCENARIO_COLORS = {
    'S1': C_S1, 'S2': C_S2, 'S3': C_S3,
    'S4': C_S4, 'S5': C_S5, 'S6': C_S6,
}

C_SHED_BAR = '#FDAE61'  # hatched shedding bar
C_DEM      = '#333333'

plt.rcParams.update({
    'font.family':      'sans-serif',
    'font.size':        10,
    'axes.titlesize':   11,
    'axes.titleweight': 'bold',
    'axes.labelsize':   10,
    'xtick.labelsize':   8,
    'ytick.labelsize':   8,
    'legend.fontsize':   8,
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



# FIGURE 1 — Wind-availability scarcity: prices + generation


def fig_scarcity(results, scenarios, base_demand):
    """
    Side-by-side:
      Left  — Zonal prices for each scenario (one line per scenario).
               Y-axis capped at PRICE_CAP; shedding-level annotated.
      Right — Generation (conventional) + wind stacked bar for each scenario,
               grouped by zone. Demand shown as dashed step line.

    Only the wet-year scenarios (S1, S2, S3) plus S4 (dry no-wind) are shown
    here to keep the scarcity figure focused on wind variability.
    Scenarios to display can be adjusted via the `show` list.
    """
    show = [sid for sid, *_ in scenarios]   # show all six by default

    nodes_sorted, labels = _node_list(results[show[0]])
    idx = np.arange(len(nodes_sorted))

    demand_arr = [base_demand.get(n, 0) for n in nodes_sorted]
    wind_arr   = [WIND_CAPACITY.get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})

    # Left: prices
    ax = axes[0]
    for sid in show:
        prices = [min(results[sid]['prices'].get(n, 0), PRICE_CAP)
                  for n in nodes_sorted]
        raw_prices = [results[sid]['prices'].get(n, 0) for n in nodes_sorted]
        ax.plot(idx, prices, 'o-', color=SCENARIO_COLORS[sid],
                lw=1.6, ms=5, label=sid)
        # Annotate shedding-level prices
        for i, (p, rp) in enumerate(zip(prices, raw_prices)):
            if rp >= CSHED * 0.95:
                ax.annotate(f'{rp/1e3:.1f}k\n€/MWh',
                            xy=(i, PRICE_CAP),
                            xytext=(i + 0.3, PRICE_CAP * 0.88),
                            fontsize=7, color=SCENARIO_COLORS[sid],
                            fontweight='bold',
                            arrowprops=dict(arrowstyle='->', lw=0.8,
                                            color=SCENARIO_COLORS[sid]))

    if PRICE_CAP < CSHED:
        ax.axhline(PRICE_CAP, color='grey', ls=':', lw=0.8, alpha=0.7)
        ax.text(len(nodes_sorted) - 0.5, PRICE_CAP * 1.01,
                f'Display cap ({PRICE_CAP} €/MWh)',
                ha='right', fontsize=7, color='grey')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel(f'Zonal price (€/MWh, cap {PRICE_CAP})')
    ax.set_title('Zonal Prices — All Scarcity Scenarios (FBMC)')
    ax.set_ylim(0, PRICE_CAP * 1.20)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(alpha=0.3)
    _country_bands(ax)

    # Right: generation stacked bars 
    ax = axes[1]
    # Offset each scenario group slightly around its node x-position
    n_show = len(show)
    bw     = min(0.8 / n_show, 0.18)
    offsets = np.linspace(-(n_show - 1) * bw / 2,
                           (n_show - 1) * bw / 2, n_show)

    for k, sid in enumerate(show):
        gen   = [results[sid]['gen'].get(n, 0)  for n in nodes_sorted]
        shed  = [results[sid]['shed'].get(n, 0) for n in nodes_sorted]
        # Wind displayed only for wind scenarios (S2, S3, S5, S6)
        has_wind = any(results[sid]['shed'].get(n, 0) == 0
                       and results[sid]['gen'].get(n, 0) <
                       results['S1']['gen'].get(n, 0) - 100
                       for n in nodes_sorted)

        x = idx + offsets[k]
        ax.bar(x, [g/1e3 for g in gen], bw,
               color=SCENARIO_COLORS[sid], edgecolor='white',
               linewidth=.4, label=sid)
        if any(s > 0.1 for s in shed):
            ax.bar(x, [s/1e3 for s in shed], bw,
                   bottom=[g/1e3 for g in gen],
                   color=C_SHED_BAR, edgecolor='white',
                   linewidth=.4, hatch='///')

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand_arr] + [demand_arr[-1]/1e3],
            where='post', color=C_DEM, lw=1.3, ls='--', label='Base demand')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — All Scarcity Scenarios (FBMC)')
    # Add shedding proxy to legend
    handles, lbls = ax.get_legend_handles_labels()
    handles.append(Patch(color=C_SHED_BAR, hatch='///', label='Shedding'))
    ax.legend(handles=handles, loc='upper right', fontsize=7.5, framealpha=0.9)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    fig.suptitle('Task 4-3 — Supply Scarcity Scenario Summary (FBMC)',
                 fontsize=12, fontweight='bold', y=1.01)
    _savefig(fig, 'fig_43_scarcity')



# FIGURE 2 — Compound scarcity deep-dive (S1 reference vs S6 worst case)
# ══════════════════════════════════════════════════════════════════════════════

def fig_compound(results, base_demand):
    """
    Side-by-side comparing reference (S1: wet, no wind) vs worst compound
    scenario (S6: dry, full wind, peak demand):
      Left  — Generation + shedding stacked bars.
      Right — Zonal prices (capped; shedding annotated).

    Highlights which zones shed and why prices spike system-wide.
    Data pulled entirely from live solver result dicts.
    """
    ref_sid  = 'S1'
    comp_sid = 'S6'

    nodes_sorted, labels = _node_list(results[ref_sid])
    idx = np.arange(len(nodes_sorted))

    ref_gen    = [results[ref_sid]['gen'].get(n, 0)   for n in nodes_sorted]
    comp_gen   = [results[comp_sid]['gen'].get(n, 0)  for n in nodes_sorted]
    comp_shed  = [results[comp_sid]['shed'].get(n, 0) for n in nodes_sorted]
    ref_price  = [results[ref_sid]['prices'].get(n, 0) for n in nodes_sorted]
    comp_price = [results[comp_sid]['prices'].get(n, 0) for n in nodes_sorted]
    demand_arr = [base_demand.get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})
    bw = 0.34

    # Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in ref_gen], bw,
           label=f'{ref_sid}: Wet, no wind, base demand',
           color=SCENARIO_COLORS[ref_sid], edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [g/1e3 for g in comp_gen], bw,
           label=f'{comp_sid}: Dry, full wind, demand ×{PEAK_SCALE}',
           color=SCENARIO_COLORS[comp_sid], edgecolor='white', linewidth=.6)
    # Stack shedding on top of compound gen
    ax.bar(idx + bw/2, [s/1e3 for s in comp_shed], bw,
           bottom=[g/1e3 for g in comp_gen],
           color=C_SHED_BAR, edgecolor='white', linewidth=.6,
           hatch='///', label='Load shedding')

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand_arr] + [demand_arr[-1]/1e3],
            where='post', color=C_DEM, lw=1.3, ls='--', label='Base demand')

    # Annotate shedding zones
    for i, (shed, n) in enumerate(zip(comp_shed, nodes_sorted)):
        if shed > 0.1:
            top = (comp_gen[i] + shed) / 1e3
            ax.annotate(f'{labels[i]}: {shed:.0f} MW\nshed',
                        xy=(i + bw/2, top),
                        xytext=(i + bw/2 + 0.6, top + 0.5),
                        fontsize=8, color=C_SHED_BAR,
                        fontweight='bold',
                        arrowprops=dict(arrowstyle='->', lw=0.9,
                                        color=C_SHED_BAR))

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation — Reference vs. Compound Scarcity (FBMC)')
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    # Right: prices 
    ax = axes[1]
    # Reference prices: normal bars
    ax.bar(idx - bw/2, ref_price, bw,
           label=f'{ref_sid}: reference',
           color=SCENARIO_COLORS[ref_sid], edgecolor='white', linewidth=.6)

    # Compound prices: capped; full shedding-price zones shown at cap
    comp_display = [min(p, PRICE_CAP) for p in comp_price]
    comp_bar_colors = ['#B2182B' if p >= CSHED * 0.95
                       else SCENARIO_COLORS[comp_sid]
                       for p in comp_price]
    for i in range(len(nodes_sorted)):
        ax.bar(i + bw/2, comp_display[i], bw,
               color=comp_bar_colors[i], edgecolor='white', linewidth=.6)

    # Annotate shedding-price bars
    for i, p in enumerate(comp_price):
        if p >= CSHED * 0.95:
            ax.text(i + bw/2, PRICE_CAP * 0.98,
                    f'{p/1e3:.1f}k\n€/MWh',
                    ha='center', va='top', fontsize=7,
                    color='white', fontweight='bold')

    # Proxy for legend
    ax.bar([], [], color=SCENARIO_COLORS[comp_sid],
           label=f'{comp_sid}: compound (normal)')
    ax.bar([], [], color='#B2182B',
           label=f'{comp_sid}: compound (shedding price)')

    if PRICE_CAP < CSHED:
        ax.axhline(PRICE_CAP, color='grey', ls=':', lw=0.8, alpha=0.7)
        ax.text(len(nodes_sorted) - 0.5, PRICE_CAP * 1.01,
                f'Display cap ({PRICE_CAP} €/MWh)',
                ha='right', fontsize=7, color='grey')

    ax.set_ylim(0, PRICE_CAP * 1.20)
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel(f'Zonal price (€/MWh, cap {PRICE_CAP})')
    ax.set_title('Prices — Reference vs. Compound Scarcity (FBMC)')
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    fig.suptitle('Task 4-3 — Compound Scarcity Deep-Dive (S1 vs S6, FBMC)',
                 fontsize=12, fontweight='bold', y=1.01)
    _savefig(fig, 'fig_43_compound')



# main


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
        ("S1", "Wet, no wind, base demand",              DATA_WET, True, None),
        ("S2", "Wet, full wind, base demand",             DATA_WET, True, net_wet),
        ("S3", f"Wet, full wind, demand×{PEAK_SCALE}",   DATA_WET, True, net_peak_wet),
        ("S4", "Dry, no wind, base demand",              DATA_DRY, True, None),
        ("S5", "Dry, full wind, base demand",             DATA_DRY, True, net_dry),
        ("S6", f"Dry, full wind, demand×{PEAK_SCALE}",   DATA_DRY, True, net_peak_dry),
    ]

    results = {}
    for sid, label, fname, dcflow, demand_ov in scenarios:
        print(f"\n>>> [{sid}] {label} ...")
        results[sid] = solve_nordic(fname, dcflow=dcflow,
                                    demand_override=demand_ov)
        _, total_cr = compute_congestion_rent(results[sid])
        shed = sum(results[sid]["shed"].values())
        print(f"    Cost: {results[sid]['objective']:,.0f} €/h  |  "
              f"CR: {total_cr:,.0f} €/h  |  Shed: {shed:.1f} MW")

    # Table A.13
    names = results["S1"]["node_names"]
    print("\n\n" + "=" * 90)
    print("  Table A.13 — Supply Scarcity: Compound Scenario Comparison (FBMC)")
    print("=" * 90)

    print(f"\n  {'Scenario':<6} {'Description':<40} "
          f"{'Cost [€/h]':>12} {'CR [€/h]':>10} {'Shed [MW]':>10}")
    print(f"  {'-'*6} {'-'*40} {'-'*12} {'-'*10} {'-'*10}")
    for sid, label, _, _, _ in scenarios:
        res = results[sid]
        _, total_cr = compute_congestion_rent(res)
        shed = sum(res["shed"].values())
        print(f"  {sid:<6} {label:<40} "
              f"{res['objective']:>12,.0f} {total_cr:>10,.0f} {shed:>10.2f}")

    print(f"\n  Nodal Prices [€/MWh]:")
    print(f"  {'Node':<5} {'Name':<6}" +
          "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['prices'][n]:>8.2f}"
        print(row)

    print(f"\n  Generation [MW]:")
    print(f"  {'Node':<5} {'Name':<6}" +
          "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['gen'][n]:>8.1f}"
        print(row)

    print(f"\n  Load Shedding [MW]:")
    print(f"  {'Node':<5} {'Name':<6}" +
          "".join(f" {sid:>8}" for sid, *_ in scenarios))
    print(f"  {'-'*5} {'-'*6}" + "  ------" * len(scenarios))
    for n in sorted(names):
        row = f"  {n:<5} {names[n]:<6}"
        for sid, *_ in scenarios:
            row += f" {results[sid]['shed'][n]:>8.2f}"
        print(row)

    print("\n\n" + "=" * 72)
    print("  Key Observations")
    print("=" * 72)
    cost_s1 = results["S1"]["objective"]
    for sid, label, _, _, _ in scenarios[1:]:
        delta = results[sid]["objective"] - cost_s1
        print(f"  [{sid}] {label:<40} ΔCost vs S1: {delta:>+12,.0f} €/h")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_scarcity(results, scenarios, base_wet)
    fig_compound(results, base_wet)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
