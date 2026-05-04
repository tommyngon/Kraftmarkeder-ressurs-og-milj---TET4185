"""
Task 3-3 — Dry Year: FBMC and ATC market clearing

Solves the Nordic 12-node market for the dry year using both FBMC and ATC.
The dry year Excel file has reduced hydro generation capacities throughout
the Nordic system.

Reproduces:
  Table A.3  — Generation and nodal prices (dry year, both methods)
  Table A.4  — AC line flows and congestion rent (dry year, both methods)
  Table A.5  — Wet vs. Dry year comparison
  fig_33_dry_gen_prices.pdf/.png  — Generation dispatch + zonal prices (dry year)
  fig_33_dry_ac_flows.pdf/.png    — AC line flows FBMC vs ATC (dry year)
  fig_33c_wet_vs_dry.pdf/.png     — Wet vs. Dry year comparison (FBMC prices + gen)

Run

    cd code/
    python problem3/task3_3_dry_year.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

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
)

# Paths 
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")
DATA_DRY = os.path.join(os.path.dirname(__file__), "../data/Nordic_dry.xlsx")

# Plot style 
C_FBMC = '#2166AC'   # steel blue  (FBMC / wet)
C_ATC  = '#D6604D'   # muted red   (ATC)
C_DRY  = '#4DAC26'   # green       (dry year)
C_WET  = '#2166AC'   # same blue   (wet year, for wet-vs-dry plot)
C_DEM  = '#333333'
C_MC   = '#B2182B'
C_SHAD = '#E08214'

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


# Helper

def _savefig(fig, stem):
    """Save PDF + PNG and print paths."""
    for ext in ('pdf', 'png'):
        path = os.path.join(OUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, bbox_inches='tight')
        print(f"  Saved: {path}")
    plt.close(fig)


def _node_list(res):
    """Return sorted node indices and their zone labels."""
    names = res['node_names']
    nodes_sorted = sorted(names.keys())
    labels = [names[n] for n in nodes_sorted]
    return nodes_sorted, labels


# FIGURE 1 — Dry-year generation dispatch + zonal prices  (FBMC vs ATC)

def fig_dry_gen_prices(res_fbmc, res_atc):
    """
    Side-by-side bar chart:
      Left  — generation dispatch (FBMC blue, ATC red, demand dashed, capacity dotted)
      Right — zonal prices (FBMC blue, ATC red, marginal cost diamond)
    Data pulled directly from solver result dicts.
    """
    nodes_sorted, labels = _node_list(res_fbmc)
    idx = np.arange(len(nodes_sorted))

    fbmc_gen   = [res_fbmc['gen'].get(n, 0)     for n in nodes_sorted]
    atc_gen    = [res_atc['gen'].get(n, 0)      for n in nodes_sorted]
    demand     = [res_fbmc['demand'].get(n, 0)  for n in nodes_sorted]
    gencap     = [res_fbmc['gencap'].get(n, 0)  for n in nodes_sorted]
    gencost    = [res_fbmc['gencost'].get(n, 0) for n in nodes_sorted]
    fbmc_price = [res_fbmc['prices'].get(n, 0)  for n in nodes_sorted]
    atc_price  = [res_atc['prices'].get(n, 0)   for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})
    bw = 0.34

    # Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in fbmc_gen], bw,
           label='FBMC', color=C_FBMC, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [g/1e3 for g in atc_gen], bw,
           label='ATC',  color=C_ATC,  edgecolor='white', linewidth=.6)

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand] + [demand[-1]/1e3],
            where='post', color=C_DEM, lw=1.4, ls='--', label='Demand')
    ax.step(x_step, [c/1e3 for c in gencap] + [gencap[-1]/1e3],
            where='post', color='gray', lw=1.0, ls=':', label='Dry capacity')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — Dry Year')
    ax.legend(loc='upper right')
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)

    # Right: prices 
    ax = axes[1]
    ax.bar(idx - bw/2, fbmc_price, bw,
           label='FBMC', color=C_FBMC, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, atc_price, bw,
           label='ATC',  color=C_ATC,  edgecolor='white', linewidth=.6)
    ax.plot(idx, gencost, 'D', color=C_MC, ms=6, zorder=5,
            label='Marginal cost')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh)')
    ax.set_title('Zonal Prices — Dry Year')
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)

    _savefig(fig, 'fig_33_dry_gen_prices')


# FIGURE 2 — Dry-year AC line flows  (FBMC vs ATC)
------------------------------------------------------------------------------

def fig_dry_ac_flows(res_fbmc, res_atc):
    """
    Horizontal bar chart of AC line flows.
    Capacity envelope shown as dashed (forward) / dotted (reverse) lines.
    Data pulled directly from solver result dicts.
    Expects:
      res['ac_flows']  dict  line_label -> MW  (signed, from→to positive)
      res['ac_caps']   dict  line_label -> (cap_fwd, cap_rev)
    """
    ac_lines  = sorted(res_fbmc['ac_flows'].keys())
    n         = len(ac_lines)
    idy       = np.arange(n)
    bw2       = 0.35

    fbmc_vals = [res_fbmc['ac_flows'][l] for l in ac_lines]
    atc_vals  = [res_atc['ac_flows'][l]  for l in ac_lines]
    caps_pos  = [ res_fbmc['ac_caps'][l][0] for l in ac_lines]
    caps_neg  = [-res_fbmc['ac_caps'][l][1] for l in ac_lines]

    fig, ax = plt.subplots(figsize=(15, max(6, n * 0.55)))
    ax.barh(idy + bw2/2, fbmc_vals, bw2,
            label='FBMC', color=C_FBMC, edgecolor='white', linewidth=.5)
    ax.barh(idy - bw2/2, atc_vals,  bw2,
            label='ATC',  color=C_ATC,  edgecolor='white', linewidth=.5)

    for i, (cp, cn) in enumerate(zip(caps_pos, caps_neg)):
        ax.plot([cp, cp], [i - 0.5, i + 0.5],
                color='#B2182B', lw=1.3, ls='--',
                label='Cap (fwd)' if i == 0 else '')
        ax.plot([cn, cn], [i - 0.5, i + 0.5],
                color='#67001F', lw=1.3, ls=':',
                label='Cap (rev)' if i == 0 else '')

    ax.axvline(0, color='black', lw=0.8)
    ax.set_yticks(idy)
    ax.set_yticklabels(ac_lines, fontsize=9)
    ax.set_xlabel('Flow (MW)')
    ax.set_title('AC Line Flows — FBMC vs ATC (Dry Year)')
    ax.legend(loc='lower right', ncol=2)
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()

    _savefig(fig, 'fig_33_dry_ac_flows')



# FIGURE 3 — Wet vs. Dry year comparison  (FBMC only)
# ----------------------------------------------------------------------------

def fig_wet_vs_dry(res_wet_fbmc, res_dry_fbmc):
    """
    Side-by-side comparison between wet and dry year under FBMC:
      Left  — generation dispatch (wet blue, dry green, demand dashed)
      Right — zonal prices (wet blue, dry green, marginal cost diamonds)
    Data pulled directly from solver result dicts.
    """
    nodes_sorted, labels = _node_list(res_wet_fbmc)
    idx = np.arange(len(nodes_sorted))

    wet_gen    = [res_wet_fbmc['gen'].get(n, 0)    for n in nodes_sorted]
    dry_gen    = [res_dry_fbmc['gen'].get(n, 0)    for n in nodes_sorted]
    demand     = [res_wet_fbmc['demand'].get(n, 0) for n in nodes_sorted]
    gencost    = [res_wet_fbmc['gencost'].get(n, 0) for n in nodes_sorted]
    wet_cap    = [res_wet_fbmc['gencap'].get(n, 0) for n in nodes_sorted]
    dry_cap    = [res_dry_fbmc['gencap'].get(n, 0) for n in nodes_sorted]
    wet_price  = [res_wet_fbmc['prices'].get(n, 0) for n in nodes_sorted]
    dry_price  = [res_dry_fbmc['prices'].get(n, 0) for n in nodes_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.5),
                             gridspec_kw={'wspace': 0.30})
    bw = 0.34

    # Left: generation 
    ax = axes[0]
    ax.bar(idx - bw/2, [g/1e3 for g in wet_gen], bw,
           label='FBMC Wet', color=C_WET, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, [g/1e3 for g in dry_gen], bw,
           label='FBMC Dry', color=C_DRY, edgecolor='white', linewidth=.6)

    x_step = np.append(idx - 0.5, idx[-1] + 0.5)
    ax.step(x_step, [d/1e3 for d in demand] + [demand[-1]/1e3],
            where='post', color=C_DEM, lw=1.4, ls='--', label='Demand')

    # Show both capacities as thin steps
    ax.step(x_step, [c/1e3 for c in wet_cap] + [wet_cap[-1]/1e3],
            where='post', color=C_WET, lw=0.8, ls=':', alpha=0.5,
            label='Wet cap')
    ax.step(x_step, [c/1e3 for c in dry_cap] + [dry_cap[-1]/1e3],
            where='post', color=C_DRY, lw=0.8, ls=':', alpha=0.5,
            label='Dry cap')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — Wet vs. Dry Year (FBMC)')
    ax.legend(loc='upper right', fontsize=8)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)

    # Right: prices 
    ax = axes[1]
    ax.bar(idx - bw/2, wet_price, bw,
           label='FBMC Wet', color=C_WET, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, dry_price, bw,
           label='FBMC Dry', color=C_DRY, edgecolor='white', linewidth=.6)
    ax.plot(idx, gencost, 'D', color=C_MC, ms=6, zorder=5,
            label='Marginal cost')

    # Annotate price deltas for Norwegian zones where the shift is large
    for i, n in enumerate(nodes_sorted):
        delta = dry_price[i] - wet_price[i]
        if abs(delta) > 5:
            ypos = max(wet_price[i], dry_price[i]) + 2
            ax.text(i, ypos, f'{delta:+.0f}', ha='center', va='bottom',
                    fontsize=7.5, color='#444444')

    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh)')
    ax.set_title('Zonal Prices — Wet vs. Dry Year (FBMC)')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(axis='y', alpha=0.3)

    _savefig(fig, 'fig_33c_wet_vs_dry')


# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 72)
    print("  TASK 3-3  |  Dry Year  |  FBMC vs ATC")
    print("=" * 72)

    # FBMC
    print("\n>>> Solving FBMC (DC power flow) — Dry year ...")
    res_fbmc = solve_nordic(DATA_DRY, dcflow=True)
    print_generation_table(
        res_fbmc,
        title="Table A.3 (partial) — Dry Year, FBMC | Generation & Nodal Prices")
    print_congestion_table(
        res_fbmc,
        title="Table A.4 (partial) — Dry Year, FBMC | AC Line Flows & Congestion Rent")
    cr_fbmc, total_cr_fbmc = compute_congestion_rent(res_fbmc)
    print(f"\n  FBMC Congestion Rent total: {total_cr_fbmc:,.2f} €/h")
    print(f"  FBMC Objective (total cost): {res_fbmc['objective']:,.2f} €/h")

    # ATC
    print("\n>>> Solving ATC (transport network) — Dry year ...")
    res_atc = solve_nordic(DATA_DRY, dcflow=False)
    print_generation_table(
        res_atc,
        title="Table A.3 (partial) — Dry Year, ATC | Generation & Nodal Prices")
    print_congestion_table(
        res_atc,
        title="Table A.4 (partial) — Dry Year, ATC | AC Line Flows & Congestion Rent")
    cr_atc, total_cr_atc = compute_congestion_rent(res_atc)
    print(f"\n  ATC Congestion Rent total: {total_cr_atc:,.2f} €/h")
    print(f"  ATC Objective (total cost): {res_atc['objective']:,.2f} €/h")

    # Wet year baseline
    print("\n>>> Solving FBMC — Wet year (for comparison) ...")
    res_wet_fbmc = solve_nordic(DATA_WET, dcflow=True)
    res_wet_atc  = solve_nordic(DATA_WET, dcflow=False)
    cr_wet_fbmc, total_cr_wet_fbmc = compute_congestion_rent(res_wet_fbmc)
    cr_wet_atc,  total_cr_wet_atc  = compute_congestion_rent(res_wet_atc)

    # Summary (Table A.5)
    print("\n\n" + "=" * 80)
    print("  Table A.5 — Wet vs. Dry Year Comparison")
    print("=" * 80)
    print(f"  {'Metric':<40} {'Wet FBMC':>10} {'Dry FBMC':>10} "
          f"{'Wet ATC':>10} {'Dry ATC':>10}")
    print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'System cost [€/h]':<40} "
          f"{res_wet_fbmc['objective']:>10,.0f} {res_fbmc['objective']:>10,.0f} "
          f"{res_wet_atc['objective']:>10,.0f} {res_atc['objective']:>10,.0f}")
    print(f"  {'Total congestion rent [€/h]':<40} "
          f"{total_cr_wet_fbmc:>10,.0f} {total_cr_fbmc:>10,.0f} "
          f"{total_cr_wet_atc:>10,.0f} {total_cr_atc:>10,.0f}")
    print(f"  {'Total load shedding [MW]':<40} "
          f"{sum(res_wet_fbmc['shed'].values()):>10.2f} "
          f"{sum(res_fbmc['shed'].values()):>10.2f} "
          f"{sum(res_wet_atc['shed'].values()):>10.2f} "
          f"{sum(res_atc['shed'].values()):>10.2f}")

    names = res_fbmc["node_names"]
    print(f"\n  Nodal prices (FBMC):")
    print(f"  {'Node':<5} {'Name':<6} {'Wet':>8} {'Dry':>8} {'Δ':>8}")
    print(f"  {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for n in sorted(res_fbmc["prices"]):
        pw  = res_wet_fbmc["prices"][n]
        pd_ = res_fbmc["prices"][n]
        print(f"  {n:<5} {names[n]:<6} {pw:>8.2f} {pd_:>8.2f} {pd_-pw:>+8.2f}")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_dry_gen_prices(res_fbmc, res_atc)
    fig_dry_ac_flows(res_fbmc, res_atc)
    fig_wet_vs_dry(res_wet_fbmc, res_fbmc)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
