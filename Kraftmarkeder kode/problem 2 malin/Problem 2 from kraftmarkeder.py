#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TET4185 – Course Project (Spring 2026)
Problem 2.4b/c: Social Welfare Maximization with flexible loads

Extends the DCOPF from Task 2-4a by changing the objective from cost
minimisation to social welfare maximisation:

    max  sum_{d in flex} WTP_d * P_d  -  sum_g c_g * P_g

Inflexible loads (Load 1, Load 3) are modelled as fixed equality constraints.
Flexible loads (Load 2_1, 2_2, 2_3) are bounded: 0 <= P_d <= D_d_max.

Generator data: "Problem 2.3 - Generators" sheet.
Load data:      "Problem 2.4 - Loads" sheet.
Per-unit base: 1000 MVA. Solver: Gurobi.
"""

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ==========================================================
# 1. Read system data from Excel
# ==========================================================

file_path = "Problem 2 data.xlsx"

# Generators (from 2.3 sheet, rows 3-7, cols 0-3)
df_gen = pd.read_excel(file_path, sheet_name="Problem 2.3 - Generators", header=None)
n_gens = 5
gen_names = df_gen.iloc[3:3+n_gens, 0].tolist()
gen_caps  = df_gen.iloc[3:3+n_gens, 1].astype(float).tolist()
gen_costs = df_gen.iloc[3:3+n_gens, 2].astype(float).tolist()
gen_locs  = [int(str(s).split()[-1]) for s in df_gen.iloc[3:3+n_gens, 3]]

generators = {}
for i, name in enumerate(gen_names):
    generators[name] = {'node': gen_locs[i], 'cost': gen_costs[i], 'cap': gen_caps[i]}

# Loads (from 2.4 sheet, rows 3-7, cols 9-12)
# Col 9=name, 10=demand, 11=WTP, 12=location
df_load = pd.read_excel(file_path, sheet_name="Problem 2.4 - Loads", header=None)
n_loads = 5
load_names_list = df_load.iloc[3:3+n_loads, 9].tolist()
load_demands    = df_load.iloc[3:3+n_loads, 10].astype(float).tolist()
load_wtp_raw    = df_load.iloc[3:3+n_loads, 11].tolist()
load_nodes      = [int(str(s).split()[-1]) for s in df_load.iloc[3:3+n_loads, 12]]

loads = {}
for i, name in enumerate(load_names_list):
    wtp_str = str(load_wtp_raw[i]).strip().upper()
    if wtp_str in ('NAN', 'NONE', 'NA', ''):
        wtp, flexible = None, False
    else:
        wtp, flexible = float(load_wtp_raw[i]), True
    loads[name] = {
        'node': load_nodes[i], 'demand': load_demands[i],
        'wtp': wtp, 'flexible': flexible
    }

load_names   = list(loads.keys())
flex_loads   = [l for l in load_names if loads[l]['flexible']]
inflex_loads = [l for l in load_names if not loads[l]['flexible']]

# Lines (from 2.4 sheet, rows 3-5, cols 15-17)
line_cap_list  = df_load.iloc[3:6, 16].astype(float).tolist()
line_susc_list = df_load.iloc[3:6, 17].astype(float).tolist()
line_keys = []
for s in df_load.iloc[3:6, 15]:
    parts = str(s).split()[-1].split('-')
    line_keys.append((int(parts[0]), int(parts[1])))

susceptance   = dict(zip(line_keys, line_susc_list))
line_capacity = dict(zip(line_keys, line_cap_list))

nodes = [1, 2, 3]
lines = sorted(line_keys)
g_names = list(generators.keys())

# ==========================================================
# 2. Build and solve the SW maximization model
# ==========================================================

model = pyo.ConcreteModel("SW_Task2_4c")

model.N = pyo.Set(initialize=nodes)
model.G = pyo.Set(initialize=g_names)
model.L = pyo.Set(initialize=lines)

# Decision variables
model.Pg    = pyo.Var(model.G, domain=pyo.NonNegativeReals)      # generator output
model.Pd    = pyo.Var(load_names, domain=pyo.NonNegativeReals)   # load served
model.theta = pyo.Var(model.N)
model.flow  = pyo.Var(model.L)

# Objective: maximise social welfare
model.objective = pyo.Objective(
    expr=(sum(loads[l]['wtp'] * model.Pd[l] for l in flex_loads)
          - sum(generators[g]['cost'] * model.Pg[g] for g in model.G)),
    sense=pyo.maximize)

# Inflexible loads: must be fully served
def inflex_rule(m, l):
    return m.Pd[l] == loads[l]['demand']
model.inflex_load = pyo.Constraint(inflex_loads, rule=inflex_rule)

# Flexible load capacity: 0 <= P_d <= D_max
def flex_rule(m, l):
    return m.Pd[l] <= loads[l]['demand']
model.flex_cap = pyo.Constraint(flex_loads, rule=flex_rule)

# Generator capacity
def gen_rule(m, g):
    return m.Pg[g] <= generators[g]['cap']
model.gen_limit = pyo.Constraint(model.G, rule=gen_rule)

# DC power flow
def flow_rule(m, i, j):
    return m.flow[i, j] == susceptance[(i, j)] * (m.theta[i] - m.theta[j])
model.flow_def = pyo.Constraint(model.L, rule=flow_rule)

# Line capacity
def line_rule(m, i, j):
    return (-line_capacity[(i, j)], m.flow[i, j], line_capacity[(i, j)])
model.line_limit = pyo.Constraint(model.L, rule=line_rule)

# Power balance (dual = nodal price; sign flip needed for max problem)
def balance_rule(m, n):
    gen  = sum(m.Pg[g] for g in model.G if generators[g]['node'] == n)
    load = sum(m.Pd[l] for l in load_names if loads[l]['node'] == n)
    out  = sum(m.flow[i, j] for (i, j) in model.L if i == n)
    inp  = sum(m.flow[i, j] for (i, j) in model.L if j == n)
    return gen - load == out - inp
model.balance = pyo.Constraint(model.N, rule=balance_rule)

# Reference bus
model.theta[1].fix(0)

# Duals
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

# Solve
solver = pyo.SolverFactory("gurobi")
results = solver.solve(model)
assert results.solver.termination_condition == pyo.TerminationCondition.optimal

# ==========================================================
# 3. Print results
# ==========================================================

# In a maximization problem, nodal price = -dual of balance constraint
nodal_prices = {n: -model.dual[model.balance[n]] for n in nodes}

print("=" * 60)
print("  Task 2-4c: Social Welfare Maximization")
print("=" * 60)

print("\n--- Generator dispatch ---")
for g in g_names:
    pg = pyo.value(model.Pg[g])
    cap = generators[g]['cap']
    status = "At capacity" if pg >= cap - 0.01 \
        else ("Not dispatched" if pg < 0.01 else "Partial")
    print(f"  {g:8s} (Node {generators[g]['node']}, "
          f"{generators[g]['cost']:.0f} NOK/MWh): "
          f"{pg:8.2f} MW  [{status}]")

print("\n--- Load served ---")
for l in load_names:
    pd_val = pyo.value(model.Pd[l])
    dmax = loads[l]['demand']
    if loads[l]['flexible']:
        status = "Fully served" if pd_val >= dmax - 0.01 \
            else ("Curtailed" if pd_val < 0.01 else f"Partial ({pd_val:.0f} MW)")
        wtp_str = f"WTP={loads[l]['wtp']:.0f}"
    else:
        status = "Inflexible"
        wtp_str = "inflexible"
    print(f"  {l:10s} ({wtp_str}): {pd_val:8.2f} MW  (max: {dmax:.0f})  [{status}]")

print("\n--- Nodal prices ---")
for n in nodes:
    print(f"  Node {n}: {nodal_prices[n]:8.2f} NOK/MWh")

print("\n--- Line flows ---")
for (i, j) in lines:
    f_val = pyo.value(model.flow[i, j])
    cap = line_capacity[(i, j)]
    binding = abs(abs(f_val) - cap) < 0.01
    print(f"  Line {i}-{j}: {f_val:8.2f} MW"
          f"{'  ** BINDING **' if binding else ''}")

# Social welfare
total_utility  = sum(loads[l]['wtp'] * pyo.value(model.Pd[l]) for l in flex_loads)
total_gen_cost = sum(generators[g]['cost'] * pyo.value(model.Pg[g]) for g in g_names)
sw = total_utility - total_gen_cost
print(f"\n  Consumer utility: {total_utility:,.0f} NOK")
print(f"  Generation cost:  {total_gen_cost:,.0f} NOK")
print(f"  Social welfare:   {sw:,.0f} NOK")

# Shadow prices
print("\n--- Shadow prices of binding constraints ---")
for g in g_names:
    d = model.dual[model.gen_limit[g]]
    if abs(d) > 1e-6:
        print(f"  {g} capacity: {d:.2f} NOK/MW")
for l in flex_loads:
    d = model.dual[model.flex_cap[l]]
    if abs(d) > 1e-6:
        print(f"  {l} cap: {d:.2f} NOK/MW  (fully served)")

# ==========================================================
# 4. Plot
# ==========================================================

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Left: generation dispatch
ax1 = axes[0]
colors = ['#2196F3', '#64B5F6', '#B0BEC5', '#F44336', '#4CAF50']
x = np.arange(len(nodes))
bar_width = 0.5
bottoms = np.zeros(len(nodes))
patches = []

for idx, g in enumerate(g_names):
    n_idx = generators[g]['node'] - 1
    pg = pyo.value(model.Pg[g])
    heights = np.zeros(len(nodes))
    heights[n_idx] = pg
    ax1.bar(x, heights, bar_width, bottom=bottoms,
            color=colors[idx], edgecolor='white', linewidth=0.8)
    bottoms[n_idx] += pg
    patches.append(mpatches.Patch(
        color=colors[idx],
        label=f"{g.replace('_',',')} ({generators[g]['cost']:.0f} NOK/MWh)"))

for i, n in enumerate(nodes):
    total_gen = sum(pyo.value(model.Pg[g])
                    for g in g_names if generators[g]['node'] == n)
    total_load = sum(pyo.value(model.Pd[l])
                     for l in load_names if loads[l]['node'] == n)
    y_pos = max(total_gen, total_load) + 20
    ax1.text(i, y_pos, f"\u03bb = {nodal_prices[n]:.0f} NOK/MWh",
             ha='center', va='bottom', fontsize=9, fontweight='bold')

demand_served = [sum(pyo.value(model.Pd[l]) for l in load_names
                     if loads[l]['node'] == n) for n in nodes]
ax1.hlines(demand_served, x - bar_width/2, x + bar_width/2,
           colors='black', linestyles='--', linewidth=1.5)
patches.append(plt.Line2D([0], [0], color='black', linestyle='--',
                           linewidth=1.5, label='Load served'))
ax1.set_xticks(x)
ax1.set_xticklabels([f'Node {n}' for n in nodes])
ax1.set_ylabel('Power [MW]')
ax1.set_title('Generation Dispatch')
ax1.legend(handles=patches, fontsize=8, loc='upper right')
ax1.set_ylim(0, max(max(bottoms), max(demand_served)) * 1.3)
ax1.grid(axis='y', alpha=0.3)

# Right: flexible load served vs max
ax2 = axes[1]
x2 = np.arange(len(flex_loads))
bar_width2 = 0.4
max_vals = [loads[l]['demand'] for l in flex_loads]
served_vals = [pyo.value(model.Pd[l]) for l in flex_loads]
wtp_vals = [loads[l]['wtp'] for l in flex_loads]

ax2.bar(x2, max_vals, bar_width2, color='lightgrey', edgecolor='black',
        linewidth=0.8, label='Max demand')
ax2.bar(x2, served_vals, bar_width2,
        color=['#FF9800', '#FF5722', '#9C27B0'],
        edgecolor='white', linewidth=0.8, label='Served')
for i, wtp in enumerate(wtp_vals):
    ax2.text(i, max_vals[i] + 8, f"WTP={wtp:.0f}",
             ha='center', va='bottom', fontsize=9)

ax2.set_xticks(x2)
ax2.set_xticklabels([l.replace('_', ',') for l in flex_loads])
ax2.set_ylabel('Power [MW]')
ax2.set_title('Flexible Load Served vs Max Demand\n(Node 2)')
ax2.legend(fontsize=9)
ax2.set_ylim(0, max(max_vals) * 1.35)
ax2.grid(axis='y', alpha=0.3)

fig.suptitle('Task 2-4c: Social Welfare Maximization', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('task_2_4c_results.png', dpi=150, bbox_inches='tight')
plt.show()
