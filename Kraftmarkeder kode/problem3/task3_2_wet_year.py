"""
Task 3-2 — Wet Year: FBMC and ATC market clearing

Solves the Nordic 12-node market for the wet year using both:
  - FBMC (DC power flow / PTDF-based DCOPF)
  - ATC  (Available Transfer Capacity / transport network)

Reproduces:
  Table A.1  — Generation and nodal prices (wet year, both methods)
  Table A.2  — AC line flows and congestion rent (wet year, both methods)
  fig_32_gen_prices.pdf/.png   — Generation dispatch + zonal prices
  fig_32_ac_flows.pdf/.png     — AC line flows (FBMC vs ATC)
  fig_32_dc_flows.pdf/.png     — HVDC link flows (FBMC vs ATC)
  fig_32_shadow_prices.pdf/.png — Shadow prices of binding AC constraints

Run
---
    cd code/
    python problem3/task3_2_wet_year.py
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

# Output directory: same folder as this script 
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_WET = os.path.join(os.path.dirname(__file__), "../data/Nordic_wet.xlsx")

# Plot style 
C_FBMC = '#2166AC'   # steel blue
C_ATC  = '#D6604D'   # muted red
C_DEM  = '#333333'
C_MC   = '#B2182B'
C_SHAD = '#E08214'

plt.rcParams.update({
    'font.family':       'sans-serif',
    'font.size':         10,
    'axes.titlesize':    12,
    'axes.titleweight':  'bold',
    'axes.labelsize':    11,
    'xtick.labelsize':    9,
    'ytick.labelsize':    9,
    'legend.fontsize':    9,
    'figure.dpi':        200,
})


# Figure generator

def _savefig(fig, stem):
    """Save PDF + PNG and print paths."""
    for ext in ('pdf', 'png'):
        path = os.path.join(OUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, bbox_inches='tight')
        print(f"  Saved: {path}")
    plt.close(fig)


def fig_gen_prices(res_fbmc, res_atc):
    """
    Figure: Generation dispatch (left) and zonal prices (right).
    Uses solver result dicts directly.
    """
    names   = res_fbmc['node_names']          # dict  node_idx -> label
    nodes   = [names[n] for n in sorted(names)]
    n_nodes = len(nodes)
    idx     = np.arange(n_nodes)

    # Pull generation, demand, capacity, marginal cost, price from results
    fbmc_gen   = [res_fbmc['gen'].get(n, 0)    for n in sorted(names)]
    atc_gen    = [res_atc['gen'].get(n, 0)     for n in sorted(names)]
    demand     = [res_fbmc['demand'].get(n, 0) for n in sorted(names)]
    gencap     = [res_fbmc['gencap'].get(n, 0) for n in sorted(names)]
    gencost    = [res_fbmc['gencost'].get(n, 0) for n in sorted(names)]
    fbmc_price = [res_fbmc['prices'].get(n, 0) for n in sorted(names)]
    atc_price  = [res_atc['prices'].get(n, 0)  for n in sorted(names)]

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
            where='post', color='gray', lw=1.0, ls=':', label='Capacity')

    ax.set_xticks(idx)
    ax.set_xticklabels(nodes, rotation=45, ha='right')
    ax.set_ylabel('Generation (GW)')
    ax.set_title('Generation Dispatch — Wet Year')
    ax.legend(loc='upper right')
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis='y', alpha=0.3)

    # Right: prices 
    ax = axes[1]
    ax.bar(idx - bw/2, fbmc_price, bw,
           label='FBMC', color=C_FBMC, edgecolor='white', linewidth=.6)
    ax.bar(idx + bw/2, atc_price,  bw,
           label='ATC',  color=C_ATC,  edgecolor='white', linewidth=.6)
    ax.plot(idx, gencost, 'D', color=C_MC, ms=6, zorder=5,
            label='Marginal cost')

    ax.set_xticks(idx)
    ax.set_xticklabels(nodes, rotation=45, ha='right')
    ax.set_ylabel('Price (€/MWh)')
    ax.set_title('Zonal Prices — Wet Year')
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)

    _savefig(fig, 'fig_32_gen_prices')


def fig_ac_flows(res_fbmc, res_atc):
    """
    Figure: AC line flows for all lines, FBMC vs ATC, with capacity envelope.
    Expects res['ac_flows'] = dict  line_label -> MW  (signed, from→to positive)
    and     res['ac_caps']  = dict  line_label -> (cap_from, cap_to)
    """
    # Build a consistent ordered list of AC lines from the FBMC result
    ac_lines = sorted(res_fbmc['ac_flows'].keys())
    n = len(ac_lines)
    idy = np.arange(n)
    bw2 = 0.35

    fbmc_vals = [res_fbmc['ac_flows'][l] for l in ac_lines]
    atc_vals  = [res_atc['ac_flows'][l]  for l in ac_lines]
    caps_pos  = [res_fbmc['ac_caps'][l][0] for l in ac_lines]
    caps_neg  = [-res_fbmc['ac_caps'][l][1] for l in ac_lines]

    fig, ax = plt.subplots(figsize=(7, max(6, n * 0.55)))
    ax.barh(idy + bw2/2, fbmc_vals, bw2,
            label='FBMC', color=C_FBMC, edgecolor='white', linewidth=.5)
    ax.barh(idy - bw2/2, atc_vals,  bw2,
            label='ATC',  color=C_ATC,  edgecolor='white', linewidth=.5)

    for i, (cp, cn) in enumerate(zip(caps_pos, caps_neg)):
        ax.plot([cp, cp], [i - 0.5, i + 0.5], color='#B2182B', lw=1.2, ls='--')
        ax.plot([cn, cn], [i - 0.5, i + 0.5], color='#67001F', lw=1.2, ls=':')

    ax.axvline(0, color='black', lw=0.8)
    ax.set_yticks(idy)
    ax.set_yticklabels(ac_lines, fontsize=9)
    ax.set_xlabel('Flow (MW)')
    ax.set_title('AC Line Flows — FBMC vs ATC (Wet Year)')
    ax.legend(loc='lower right')
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()

    _savefig(fig, 'fig_32_ac_flows')


def fig_dc_flows(res_fbmc, res_atc):
    """
    Figure: HVDC link flows, FBMC vs ATC.
    Expects res['dc_flows'] = dict  link_label -> MW
    and     res['dc_caps']  = dict  link_label -> cap (positive direction)
    """
    dc_links = sorted(res_fbmc['dc_flows'].keys())
    nd = len(dc_links)
    idd = np.arange(nd)
    bw3 = 0.30

    fbmc_dc = [res_fbmc['dc_flows'][l] for l in dc_links]
    atc_dc  = [res_atc['dc_flows'][l]  for l in dc_links]
    dc_caps = [res_fbmc['dc_caps'][l]  for l in dc_links]

    fig, ax = plt.subplots(figsize=(8, 4))
    b1 = ax.bar(idd - bw3/2, fbmc_dc, bw3,
                label='FBMC', color=C_FBMC, edgecolor='white')
    b2 = ax.bar(idd + bw3/2, atc_dc,  bw3,
                label='ATC',  color=C_ATC,  edgecolor='white')

    for i, cap in enumerate(dc_caps):
        ax.hlines(cap, i - 0.5, i + 0.5,
                  colors='#B2182B', lw=1.5, ls='--',
                  label='Capacity' if i == 0 else '')

    for bar, val in zip(b1, fbmc_dc):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + abs(max(fbmc_dc + atc_dc)) * 0.02,
                f'{val:.0f}', ha='center', va='bottom',
                fontsize=9, color=C_FBMC)
    for bar, val in zip(b2, atc_dc):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + abs(max(fbmc_dc + atc_dc)) * 0.02,
                f'{val:.0f}', ha='center', va='bottom',
                fontsize=9, color=C_ATC)

    ax.set_xticks(idd)
    ax.set_xticklabels(dc_links, rotation=15, ha='right')
    ax.set_ylabel('Flow (MW)')
    ax.set_title('HVDC Link Flows — FBMC vs ATC (Wet Year)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    ymax = max(max(fbmc_dc), max(atc_dc), max(dc_caps))
    ax.set_ylim(0, ymax * 1.18)
    fig.tight_layout()

    _savefig(fig, 'fig_32_dc_flows')


def fig_shadow_prices(res_fbmc):
    """
    Figure: Shadow prices of binding AC constraints under FBMC.
    Expects res_fbmc['shadow_prices'] = dict  line_label -> shadow_price (€/MW)
    Only shows lines with shadow_price > 0.
    """
    sp_dict = {k: v for k, v in res_fbmc['shadow_prices'].items() if v > 0.01}
    if not sp_dict:
        print("  [shadow prices] No binding AC constraints found — skipping figure.")
        return

    lines  = sorted(sp_dict, key=sp_dict.get)          # ascending
    values = [sp_dict[l] for l in lines]
    caps   = [res_fbmc['ac_caps'][l][0] for l in lines]

    fig, ax = plt.subplots(figsize=(8, max(3.5, len(lines) * 0.6 + 1)))
    bars = ax.barh(lines, values, color=C_SHAD, edgecolor='white', height=0.55)

    for bar, sp_val, cap in zip(bars, values, caps):
        ax.text(bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f'{sp_val:.2f} €/MW  (cap {cap:.0f} MW)',
                va='center', fontsize=9)

    ax.set_xlabel('Shadow price (€/MW)')
    ax.set_title('Shadow Prices of Binding AC Constraints — FBMC, Wet Year')
    ax.set_xlim(0, max(values) * 1.45)
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()

    _savefig(fig, 'fig_32_shadow_prices')

# MAIN

def main():
    print("\n" + "=" * 72)
    print("  TASK 3-2  |  Wet Year  |  FBMC vs ATC")
    print("=" * 72)

    # FBMC
    print("\n>>> Solving FBMC (DC power flow) — Wet year ...")
    res_fbmc = solve_nordic(DATA_WET, dcflow=True)
    print_generation_table(
        res_fbmc,
        title="Table A.1 (partial) — Wet Year, FBMC | Generation & Nodal Prices")
    print_congestion_table(
        res_fbmc,
        title="Table A.2 (partial) — Wet Year, FBMC | AC Line Flows & Congestion Rent")
    cr_fbmc, total_cr_fbmc = compute_congestion_rent(res_fbmc)
    print(f"\n  FBMC Congestion Rent total: {total_cr_fbmc:,.2f} €/h")
    print(f"  FBMC Objective (total cost): {res_fbmc['objective']:,.2f} €/h")

    # ATC
    print("\n>>> Solving ATC (transport network) — Wet year ...")
    res_atc = solve_nordic(DATA_WET, dcflow=False)
    print_generation_table(
        res_atc,
        title="Table A.1 (partial) — Wet Year, ATC | Generation & Nodal Prices")
    print_congestion_table(
        res_atc,
        title="Table A.2 (partial) — Wet Year, ATC | AC Line Flows & Congestion Rent")
    cr_atc, total_cr_atc = compute_congestion_rent(res_atc)
    print(f"\n  ATC Congestion Rent total: {total_cr_atc:,.2f} €/h")
    print(f"  ATC Objective (total cost): {res_atc['objective']:,.2f} €/h")

    # Summary
    print("\n\n" + "=" * 72)
    print("  COMPARISON SUMMARY — Wet Year")
    print("=" * 72)
    print(f"  {'Metric':<35} {'FBMC':>12} {'ATC':>12}")
    print(f"  {'-'*35} {'-'*12} {'-'*12}")
    print(f"  {'Total system cost [€/h]':<35} "
          f"{res_fbmc['objective']:>12,.2f} {res_atc['objective']:>12,.2f}")
    print(f"  {'Total congestion rent [€/h]':<35} "
          f"{total_cr_fbmc:>12,.2f} {total_cr_atc:>12,.2f}")
    print(f"  {'Total shedding [MW]':<35} "
          f"{sum(res_fbmc['shed'].values()):>12.2f} "
          f"{sum(res_atc['shed'].values()):>12.2f}")

    names = res_fbmc["node_names"]
    print(f"\n  {'Node':<5} {'Name':<6} {'Price FBMC':>12} {'Price ATC':>12}")
    print(f"  {'-'*5} {'-'*6} {'-'*12} {'-'*12}")
    for n in sorted(res_fbmc["prices"]):
        print(f"  {n:<5} {names[n]:<6} "
              f"{res_fbmc['prices'][n]:>12.2f} {res_atc['prices'][n]:>12.2f}")

    # Figures
    print("\n\n>>> Generating figures ...")
    fig_gen_prices(res_fbmc, res_atc)
    fig_ac_flows(res_fbmc, res_atc)
    fig_dc_flows(res_fbmc, res_atc)
    fig_shadow_prices(res_fbmc)
    print("\nAll figures saved.")


if __name__ == "__main__":
    main()
