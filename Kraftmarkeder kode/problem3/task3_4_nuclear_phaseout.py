"""
Task 3-4 — Nuclear Phase-Out in SE3

Models the effect of removing nuclear capacity in SE3 (node 8).
  Base case:   GENCAP[SE3] = 12 400 MW
  Phase-out:   GENCAP[SE3] =  4 000 MW  (reduction of 8 400 MW)

This is applied on top of the wet-year base case (FBMC and ATC).

Reproduces:
  Table A.6  — Generation & prices: base vs. nuclear phase-out (FBMC)
  Table A.7  — AC line flows & congestion rent: base vs. nuclear phase-out (FBMC)
  fig_34a_nuke_phaseout.pdf/.png  — Generation dispatch + prices (base vs phaseout)
  fig_34b_gen_change.pdf/.png     — Per-zone change in generation (ΔMW)
  fig_34c_price_change.pdf/.png   — Per-zone price comparison (capped linear scale)

Run

    cd code/
    python problem3/task3_4_nuclear_phaseout.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import numpy as np

from nordic_base import (
    solve_nordic,
    print_generation_table,
    print_congestion_table,
    compute_congestion_rent,
)

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# SE3 is node 8 in the Nordic 12-node system.
SE3_NODE         = 8
SE3_BASE_CAP     = 12_400   # MW  (original full nuclear + thermal)
SE3_PHASEOUT_CAP =  4_000   # MW  (only remaining thermal, nuclear removed)

# Shedding penalty cost (must match nordic_base value)
CSHED = 3_200   # €/MWh

# Plot style 
C_BASE  = '#2166AC'   # steel blue  — base case
C_NUKE  = '#D6604D'   # muted red   — phaseout (normal price bar)
C_SHED_BAR = '#B2182B'  # dark red  — phaseout bar when shedding occurs
C_POS   = '#4DAC26'   # green  — generation increase
C_NEG   = '#D6604D'   # red    — generation decrease
C_SHED  = '#F4A582'   # orange — load shedding stacked bar
C_DEM   = '#333333'

PRICE_CAP = 200       # €/MWh — display cap for price chart (annotate above)

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

# HELPERS


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
    """Light background bands: NO (0-4), SE (5-8), FI (9), DK (10-11)."""
    bands = [(-0.5, 4.5, 'blue'), (4.5, 8.5, 'orange'),
             (8.5, 9.5, 'green'), (9.5, n_nodes - 0.5, 'red')]
    for x0, x1, c in bands:
        ax.axvspan(x0, x1, alpha=0.04, color=c)



# FIGURE A — Generation dispatch + prices side-by-side (base vs phaseout)


def fig_nuke_phaseout(res_base, res_phaseout):
    """
    Left:  Generation bars — base (blue) and phaseout (red/dark-red),
           with shedding stacked on top as hatched orange.
           Demand shown as dashed step line.
    Right: Zonal prices on a LOG scale so shedding-level prices are visible.
           Dashed horizontal line at shedding penalty cost.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    base_gen   = [res_base['gen'].get(n, 0)      for n in nodes_sorted]
    po_gen     = [res_phaseout['gen'].get(n, 0)  for n in nodes_sorted]
    po_shed    = [res_phaseout['shed'].get(n, 0) for n in nodes_sorted]
    demand     = [res_base['demand'].get(n, 0)   for n in nodes_sorted]
    base_price = [res_base['prices'].get(n, 0)   for n in nodes_sorted]
    po_price   = [res_phaseout['prices'].get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.32})
    bw = 0.34

    #  Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in base_gen], bw,
           label='Base (wet)', color=C_BASE, edgecolor='white', linewidth=.6)

    # Phaseout bar colour: dark red if shedding occurs in that zone
    po_colors = [C_SHED_BAR if s > 0.1 else C_NUKE for s in po_shed]
    ax.bar(idx + bw/2, [g/1e3 for g in po_gen], bw,
           color=po_colors, edgecolor='white', linewidth=.6,
           label='_nolegend_')
    # Stack shedding on top
    ax.bar(idx + bw/2, [s/1e3 for s in po_shed], bw,
           bottom=[g/1e3 for g in po_gen],
           color=C_SHED, edgecolor='white', linewidth=.6,
           hatch='///', label='Load shedding')

    # Proxy artists for legend
    ax.bar([], [], color=C_NUKE,     label='No nuclear (gen)')
    ax.bar([], [], color=C_SHED_BAR, label='No nuclear (shedding zone)')

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand] + [demand[-1]/1e3],
            where='post', color=C_DEM, lw=1.4, ls='--', label='Demand')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — Base vs. Nuclear Phaseout')
    ax.legend(loc='upper right', fontsize=8)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    #  Right: prices (log scale) 
    ax = axes[1]
    # Clamp zeros to 1 for log scale
    base_p_log = [max(p, 1) for p in base_price]
    po_p_log   = [max(p, 1) for p in po_price]

    ax.bar(idx - bw/2, base_p_log, bw,
           label='Base (wet)', color=C_BASE, edgecolor='white', linewidth=.6)

    po_bar_colors = [C_SHED_BAR if p >= CSHED * 0.95 else C_NUKE for p in po_price]
    ax.bar(idx + bw/2, po_p_log, bw,
           color=po_bar_colors, edgecolor='white', linewidth=.6,
           label='No nuclear')

    ax.axhline(CSHED, color='grey', ls=':', lw=1.0, alpha=0.8)
    ax.text(len(nodes_sorted) - 0.5, CSHED * 1.05,
            f'Shedding cost ({CSHED:,} €/MWh)',
            ha='right', fontsize=7.5, color='grey')

    ax.set_yscale('log')
    ax.set_ylim(10, CSHED * 2)
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh, log scale)')
    ax.set_title('Zonal Prices — Base vs. Nuclear Phaseout')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(axis='y', alpha=0.3, which='both')
    _country_bands(ax)

    _savefig(fig, 'fig_34a_nuke_phaseout')



# FIGURE B — Per-zone generation change  (ΔMW bar chart)
# ══════════════════════════════════════════════════════════════════════════════

def fig_gen_change(res_base, res_phaseout):
    """
    Single bar chart showing ΔGen = Gen_phaseout - Gen_base at each zone.
    Positive (green) = more generation; negative (red) = less.
    Load shedding shown as a separate hatched orange bar stacked on the gen bar.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    base_gen = [res_base['gen'].get(n, 0)      for n in nodes_sorted]
    po_gen   = [res_phaseout['gen'].get(n, 0)  for n in nodes_sorted]
    po_shed  = [res_phaseout['shed'].get(n, 0) for n in nodes_sorted]
    delta_gen = [po_gen[i] - base_gen[i] for i in range(len(nodes_sorted))]

    colors = [C_POS if d >= 0 else C_NEG for d in delta_gen]

    fig, ax = plt.subplots(figsize=(12, 5.0))

    bars = ax.bar(idx, [d/1e3 for d in delta_gen], 0.55,
                  color=colors, edgecolor='white', linewidth=.6,
                  label='_nolegend_')

    # Stack shedding on top of the gen bar (positive side)
    ax.bar(idx, [s/1e3 for s in po_shed], 0.55,
           bottom=[max(d, 0)/1e3 for d in delta_gen],
           color=C_SHED, edgecolor='white', linewidth=.6,
           hatch='///', label='Load shedding')

    # Annotate each bar with its MW value
    for i, (bar, dg, sh) in enumerate(zip(bars, delta_gen, po_shed)):
        label_val = dg + sh
        ypos = (max(label_val, 0) + abs(label_val) * 0.02 + 50) / 1e3
        if abs(dg) > 20 or sh > 20:
            ax.text(i, ypos if dg >= 0 else (dg - 100) / 1e3,
                    f'{dg/1e3:+.2f} GW', ha='center', va='bottom',
                    fontsize=8, color=colors[i], fontweight='bold')

    ax.axhline(0, color='black', lw=0.8)
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Change in generation (GW)')
    ax.set_title('Per-Zone Generation Change — Nuclear Phaseout vs. Base Case (FBMC, Wet Year)')

    handles = [
        Patch(color=C_POS,  label='Increased generation'),
        Patch(color=C_NEG,  label='Decreased generation'),
        Patch(color=C_SHED, hatch='///', label='Load shedding'),
    ]
    ax.legend(handles=handles, loc='lower left', framealpha=0.9)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    fig.tight_layout()
    _savefig(fig, 'fig_34b_gen_change')



# FIGURE C — Per-zone price comparison (capped linear scale)
# ══════════════════════════════════════════════════════════════════════════════

def fig_price_change(res_base, res_phaseout):
    """
    Side-by-side bars: base price (blue) vs phaseout price (red/dark-red).
    Y-axis is capped at PRICE_CAP (200 €/MWh); zones at shedding cost are
    displayed at cap height with the actual value annotated above the bar.
    """
    nodes_sorted, labels = _node_list(res_base)
    idx = np.arange(len(nodes_sorted))

    base_price = [res_base['prices'].get(n, 0)      for n in nodes_sorted]
    po_price   = [res_phaseout['prices'].get(n, 0)  for n in nodes_sorted]

    # Capped display values
    po_display = [min(p, PRICE_CAP) for p in po_price]
    po_colors  = [C_SHED_BAR if p >= CSHED * 0.95 else C_NUKE for p in po_price]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    bw = 0.34

    ax.bar(idx - bw/2, base_price, bw,
           label='Base (wet)', color=C_BASE, edgecolor='white', linewidth=.6)

    for i in range(len(nodes_sorted)):
        ax.bar(i + bw/2, po_display[i], bw,
               color=po_colors[i], edgecolor='white', linewidth=.6)

    # Annotate zones where price exceeds cap
    for i, p in enumerate(po_price):
        if p > PRICE_CAP:
            # Draw a break mark and annotate actual value
            ax.plot([i + bw/2 - 0.12, i + bw/2 + 0.12],
                    [PRICE_CAP * 0.96, PRICE_CAP * 0.96],
                    color='white', lw=2.5)
            ax.plot([i + bw/2 - 0.12, i + bw/2 + 0.12],
                    [PRICE_CAP * 0.975, PRICE_CAP * 0.975],
                    color=C_SHED_BAR, lw=1.0)
            ax.annotate(f'{p:,.0f}\n€/MWh',
                        xy=(i + bw/2, PRICE_CAP),
                        xytext=(i + bw/2, PRICE_CAP * 1.01),
                        fontsize=7.5, ha='center', va='bottom',
                        color=C_SHED_BAR, fontweight='bold')

    # Proxy artists for legend
    ax.bar([], [], color=C_NUKE,     label='No nuclear (normal price)')
    ax.bar([], [], color=C_SHED_BAR, label='No nuclear (shedding price)')

    ax.set_ylim(0, PRICE_CAP * 1.25)
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel(f'Zonal price (€/MWh, capped at {PRICE_CAP})')
    ax.set_title('Zonal Prices — Base vs. Nuclear Phaseout (FBMC, Wet Year)')
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(axis='y', alpha=0.3)
    _country_bands(ax)

    fig.tight_layout()
    _savefig(fig, 'fig_34c_price_change')



# Main


def main():
    print("\n" + "=" * 72)
    print("  TASK 3-4  |  Nuclear Phase-Out (SE3: 12 400 → 4 000 MW)")
    print("=" * 72)

    # ------------------------------------------------------------------ Base
    print("\n>>> Solving BASE case (FBMC, wet year) ...")
    res_base = solve_nordic(DATA_WET, dcflow=True)
    print_generation_table(res_base,
        title="Table A.6 (left) — BASE | FBMC Wet Year")
    print_congestion_table(res_base,
        title="Table A.7 (left) — BASE | AC Flows & Congestion Rent")
    cr_base, total_cr_base = compute_congestion_rent(res_base)

    # Nuclear phase-out
    print(f"\n>>> Solving NUCLEAR PHASE-OUT "
          f"(SE3 cap: {SE3_BASE_CAP} → {SE3_PHASEOUT_CAP} MW, FBMC) ...")
    res_phaseout = solve_nordic(
        DATA_WET, dcflow=True,
        gencap_override={SE3_NODE: SE3_PHASEOUT_CAP},
    )
    print_generation_table(res_phaseout,
        title="Table A.6 (right) — NUCLEAR PHASE-OUT | FBMC Wet Year")
    print_congestion_table(res_phaseout,
        title="Table A.7 (right) — NUCLEAR PHASE-OUT | AC Flows & Congestion Rent")
    cr_po, total_cr_po = compute_congestion_rent(res_phaseout)

    # ATC versions
    print("\n>>> Solving BASE case (ATC, wet year) ...")
    res_base_atc = solve_nordic(DATA_WET, dcflow=False)
    cr_base_atc, total_cr_base_atc = compute_congestion_rent(res_base_atc)

    print(f"\n>>> Solving NUCLEAR PHASE-OUT (SE3 cap: {SE3_PHASEOUT_CAP} MW, ATC) ...")
    res_po_atc = solve_nordic(
        DATA_WET, dcflow=False,
        gencap_override={SE3_NODE: SE3_PHASEOUT_CAP},
    )
    cr_po_atc, total_cr_po_atc = compute_congestion_rent(res_po_atc)

    # Comparison table
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
    print(f"  {'System cost [€/h]  (FBMC)':<45} "
          f"{res_base['objective']:>12,.2f} {res_phaseout['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]  (FBMC)':<45} "
          f"{total_cr_base:>12,.2f} {total_cr_po:>12,.2f}")
    print(f"  {'Total shedding [MW]  (FBMC)':<45} "
          f"{sum(res_base['shed'].values()):>12.2f} "
          f"{sum(res_phaseout['shed'].values()):>12.2f}")
    print(f"  {'System cost [€/h]  (ATC)':<45} "
          f"{res_base_atc['objective']:>12,.2f} {res_po_atc['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]  (ATC)':<45} "
          f"{total_cr_base_atc:>12,.2f} {total_cr_po_atc:>12,.2f}")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_nuke_phaseout(res_base, res_phaseout)
    fig_gen_change(res_base, res_phaseout)
    fig_price_change(res_base, res_phaseout)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
