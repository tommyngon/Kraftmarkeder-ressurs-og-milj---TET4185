"""
Task 4-2 — Peak Demand Scenarios

Scales total system demand using a multiplier to simulate high-demand (peak)
conditions. The demand is scaled proportionally across all nodes:
    D_scaled[n] = scale_factor * D_base[n]

Scenarios: scale_factor ∈ {0.8, 0.9, 1.0, 1.1, 1.2, 1.3}

Run on both FBMC and ATC (wet year base).

Reproduces:
  Table A.12 — System cost, prices, congestion rent vs. demand level
  fig_42_peak_demand.pdf/.png — 4-panel summary of demand sensitivity results

Run

    cd code/
    python problem4/task4_2_peak_demand.py
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
    compute_congestion_rent,
    _read_excel,
)

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# Demand scale factors to test
DEMAND_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]

# Shedding penalty (must match nordic_base)
CSHED = 3_200   # €/MWh

# Price cap for nodal price panel (annotate above)
PRICE_CAP = 200   # €/MWh

# Plot style 
# One colour per scale factor — use a sequential palette
SCALE_COLORS = {
    0.8: '#4575B4',
    0.9: '#74ADD1',
    1.0: '#ABD9E9',
    1.1: '#FEE090',
    1.2: '#F46D43',
    1.3: '#D73027',
}

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


def scale_demand(base_demand, factor):
    """Return demand dict with all values scaled by factor."""
    return {n: d * factor for n, d in base_demand.items()}



# FIGURE — 4-panel peak demand sensitivity summary


def fig_peak_demand(results_fbmc, results_atc, base_demand):
    """
    Four-panel figure summarising the demand scaling sensitivity:

    Panel 1 (top-left):   System cost [€/h] vs. demand scale — FBMC & ATC lines.
    Panel 2 (top-right):  Total congestion rent [€/h] vs. demand scale.
    Panel 3 (bottom-left):Load shedding [MW] vs. demand scale (FBMC).
    Panel 4 (bottom-right):Nodal prices at each scale factor (FBMC) — one line
                            per zone, coloured by country group.

    All data pulled directly from the solver result dicts.
    """
    scales      = sorted(results_fbmc.keys())
    total_d     = [sum(scale_demand(base_demand, s).values()) / 1e3 for s in scales]  # GW

    obj_fbmc    = [results_fbmc[s]['objective']              for s in scales]
    obj_atc     = [results_atc[s]['objective']               for s in scales]

    cr_fbmc     = [compute_congestion_rent(results_fbmc[s])[1] for s in scales]
    cr_atc      = [compute_congestion_rent(results_atc[s])[1]  for s in scales]

    shed_fbmc   = [sum(results_fbmc[s]['shed'].values())     for s in scales]

    # Node order and labels from the 1.0x result
    res_ref     = results_fbmc[1.0]
    nodes_sorted, node_labels = _node_list(res_ref)

    # Country colour map for nodal price lines
    country_color = {}
    for n, lbl in zip(nodes_sorted, node_labels):
        if lbl.startswith('NO'):
            country_color[n] = '#2166AC'
        elif lbl.startswith('SE'):
            country_color[n] = '#E08214'
        elif lbl == 'FI':
            country_color[n] = '#4DAC26'
        else:  # DK
            country_color[n] = '#D73027'

    fig, axes = plt.subplots(2, 2, figsize=(13, 9),
                             gridspec_kw={'hspace': 0.38, 'wspace': 0.30})

    # Panel 1: System cost 
    ax = axes[0, 0]
    ax.plot(scales, [c/1e6 for c in obj_fbmc], 'o-', color='#2166AC',
            lw=1.8, ms=6, label='FBMC')
    ax.plot(scales, [c/1e6 for c in obj_atc],  's--', color='#D6604D',
            lw=1.8, ms=6, label='ATC')
    ax.set_xlabel('Demand scale factor')
    ax.set_ylabel('System cost (M€/h)')
    ax.set_title('Total System Cost vs. Demand Scale')
    ax.legend()
    ax.xaxis.set_major_locator(mticker.FixedLocator(scales))
    ax.grid(alpha=0.3)

    # Annotate shedding onset
    for i, s in enumerate(scales):
        if shed_fbmc[i] > 0.1:
            ax.annotate('shedding\nonset',
                        xy=(s, obj_fbmc[i]/1e6),
                        xytext=(s - 0.08, obj_fbmc[i]/1e6 * 0.88),
                        fontsize=7.5, color='#D73027',
                        arrowprops=dict(arrowstyle='->', color='#D73027', lw=1.0))
            break

    # Panel 2: Congestion rent 
    ax = axes[0, 1]
    ax.plot(scales, [c/1e3 for c in cr_fbmc], 'o-', color='#2166AC',
            lw=1.8, ms=6, label='FBMC')
    ax.plot(scales, [c/1e3 for c in cr_atc],  's--', color='#D6604D',
            lw=1.8, ms=6, label='ATC')
    ax.set_xlabel('Demand scale factor')
    ax.set_ylabel('Congestion rent (k€/h)')
    ax.set_title('Total Congestion Rent vs. Demand Scale')
    ax.legend()
    ax.xaxis.set_major_locator(mticker.FixedLocator(scales))
    ax.grid(alpha=0.3)

    # Panel 3: Load shedding
    ax = axes[1, 0]
    bar_colors = [SCALE_COLORS[s] for s in scales]
    bars = ax.bar(scales, shed_fbmc, width=0.07,
                  color=bar_colors, edgecolor='white', linewidth=0.6)
    for bar, val in zip(bars, shed_fbmc):
        if val > 0.1:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(shed_fbmc) * 0.01,
                    f'{val:.0f} MW', ha='center', va='bottom',
                    fontsize=8, fontweight='bold', color='#D73027')
    ax.set_xlabel('Demand scale factor')
    ax.set_ylabel('Load shedding (MW)')
    ax.set_title('Load Shedding vs. Demand Scale (FBMC)')
    ax.xaxis.set_major_locator(mticker.FixedLocator(scales))
    ax.grid(axis='y', alpha=0.3)
    if max(shed_fbmc) < 1:
        ax.set_ylim(0, 10)
        ax.text(0.5, 0.5, 'No shedding', transform=ax.transAxes,
                ha='center', va='center', fontsize=11, color='grey',
                style='italic')

    # Panel 4: Nodal price profiles 
    ax = axes[1, 1]
    for n in nodes_sorted:
        prices = [results_fbmc[s]['prices'].get(n, 0) for s in scales]
        # Cap display at PRICE_CAP; mark shedding-level with a marker
        display = [min(p, PRICE_CAP) for p in prices]
        ax.plot(scales, display,
                color=country_color[n], lw=1.2, alpha=0.8,
                label=node_labels[nodes_sorted.index(n)])
        # Mark any shedding-price points
        for si, (s, p, d) in enumerate(zip(scales, prices, display)):
            if p >= CSHED * 0.95:
                ax.plot(s, PRICE_CAP, '*', color=country_color[n], ms=10, zorder=5)
                ax.annotate(f'{p/1e3:.1f}k\n€/MWh',
                            xy=(s, PRICE_CAP),
                            xytext=(s + 0.04, PRICE_CAP * 0.95),
                            fontsize=7, color=country_color[n],
                            fontweight='bold')

    # Country proxy artists for legend
    from matplotlib.lines import Line2D
    proxies = [
        Line2D([0], [0], color='#2166AC', lw=2, label='NO'),
        Line2D([0], [0], color='#E08214', lw=2, label='SE'),
        Line2D([0], [0], color='#4DAC26', lw=2, label='FI'),
        Line2D([0], [0], color='#D73027', lw=2, label='DK'),
    ]
    ax.legend(handles=proxies, loc='upper left', framealpha=0.9)

    if PRICE_CAP < CSHED:
        ax.axhline(PRICE_CAP, color='grey', ls=':', lw=0.8, alpha=0.7)
        ax.text(scales[-1] + 0.01, PRICE_CAP,
                f'Display cap ({PRICE_CAP} €/MWh)',
                fontsize=7, va='center', color='grey')

    ax.set_xlabel('Demand scale factor')
    ax.set_ylabel(f'Zonal price (€/MWh, cap {PRICE_CAP})')
    ax.set_title('Nodal Price Profiles vs. Demand Scale (FBMC)')
    ax.xaxis.set_major_locator(mticker.FixedLocator(scales))
    ax.set_ylim(0, PRICE_CAP * 1.20)
    ax.grid(alpha=0.3)

    fig.suptitle('Task 4-2 — Peak Demand Sensitivity (FBMC & ATC, Wet Year)',
                 fontsize=13, fontweight='bold', y=1.01)

    _savefig(fig, 'fig_42_peak_demand')



# main


def main():
    print("\n" + "=" * 72)
    print("  TASK 4-2  |  Peak Demand Scenarios  |  FBMC & ATC, Wet Year")
    print("=" * 72)

    base_data   = _read_excel(DATA_WET)
    base_demand = dict(base_data["Nodes"]["DEMAND"])
    names       = base_data["Nodes"]["NNAMES"]

    results_fbmc = {}
    results_atc  = {}

    for scale in DEMAND_SCALES:
        demand_ov = scale_demand(base_demand, scale)
        total     = sum(demand_ov.values())
        print(f"\n>>> Solving FBMC — demand scale {scale:.1f}x  (total = {total:,.0f} MW) ...")
        results_fbmc[scale] = solve_nordic(DATA_WET, dcflow=True,
                                           demand_override=demand_ov)
        print(f">>> Solving ATC  — demand scale {scale:.1f}x ...")
        results_atc[scale]  = solve_nordic(DATA_WET, dcflow=False,
                                           demand_override=demand_ov)

    # Table A.12
    print("\n\n" + "=" * 100)
    print("  Table A.12 — Peak Demand Sensitivity: FBMC Results")
    print("=" * 100)
    print(f"  {'Scale':<7} {'Total D [MW]':>13} {'Cost [€/h]':>13} {'CR [€/h]':>11} "
          f"{'Shed [MW]':>10}" +
          "".join(f" {'π' + names[n]:>8}" for n in sorted(names)))
    print("  " + "-" * (44 + 8 * len(names)))

    for scale in DEMAND_SCALES:
        res     = results_fbmc[scale]
        total_d = sum(scale_demand(base_demand, scale).values())
        _, total_cr = compute_congestion_rent(res)
        row = (f"  {scale:<7.1f} {total_d:>13,.0f} {res['objective']:>13,.0f} "
               f"{total_cr:>11,.0f} {sum(res['shed'].values()):>10.2f}")
        for n in sorted(names):
            row += f" {res['prices'][n]:>8.2f}"
        print(row)

    print(f"\n\n  ATC Results:")
    print(f"  {'Scale':<7} {'Total D [MW]':>13} {'Cost [€/h]':>13} {'CR [€/h]':>11} "
          f"{'Shed [MW]':>10}" +
          "".join(f" {'π' + names[n]:>8}" for n in sorted(names)))
    print("  " + "-" * (44 + 8 * len(names)))
    for scale in DEMAND_SCALES:
        res     = results_atc[scale]
        total_d = sum(scale_demand(base_demand, scale).values())
        _, total_cr = compute_congestion_rent(res)
        row = (f"  {scale:<7.1f} {total_d:>13,.0f} {res['objective']:>13,.0f} "
               f"{total_cr:>11,.0f} {sum(res['shed'].values()):>10.2f}")
        for n in sorted(names):
            row += f" {res['prices'][n]:>8.2f}"
        print(row)

    # Detailed for 1.0x and 1.2x
    for scale in [1.0, 1.2]:
        print_generation_table(results_fbmc[scale],
                               title=f"FBMC — Demand scale {scale:.1f}x")

    # Price range summary
    print("\n\n" + "=" * 72)
    print("  Price Range Summary (FBMC): min and max nodal prices per scenario")
    print("=" * 72)
    print(f"  {'Scale':<7} {'Min Price':>10} {'Max Price':>10} "
          f"{'Spread':>10} {'Shed [MW]':>10}")
    print(f"  {'-'*7} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for scale in DEMAND_SCALES:
        prices = list(results_fbmc[scale]["prices"].values())
        shed   = sum(results_fbmc[scale]["shed"].values())
        print(f"  {scale:<7.1f} {min(prices):>10.2f} {max(prices):>10.2f} "
              f"{max(prices)-min(prices):>10.2f} {shed:>10.2f}")

    # Figure
    print("\n\n>>> Generating figure ...")
    fig_peak_demand(results_fbmc, results_atc, base_demand)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
