#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TET4185 – Course Project (Spring 2026)
Problem 2.4a: DCOPF with multiple loads at Node 2

Extends the model from Task 2-3 by adding three loads at Node 2.
All loads are treated as inflexible (must be fully served).
Total demand: D1=200, D2=700 (200+250+250), D3=500 => 1400 MW.

Generator data: "Problem 2.3 - Generators" sheet (unchanged).
Load/line data: "Problem 2.4 - Loads" sheet.
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

# Generators from Task 2-3 sheet (rows 3-7, cols 0-3)
df_gen = pd.read_excel(file_path, sheet_name="Problem 2.3 - Generators", header=None)
n_gens = 5
gen_names = df_gen.iloc[3:3+n_gens, 0].tolist()
gen_caps  = df_gen.iloc[3:3+n_gens, 1].astype(float).tolist()
gen_costs = df_gen.iloc[3:3+n_gens, 2].astype(float).tolist()
gen_locs  = [int(str(s).split()[-1]) for s in df_gen.iloc[3:3+n_gens, 3]]

generators = {}
for i, name in enumerate(gen_names):
    generators[name] = {'node': gen_locs[i], 'cost': gen_costs[i], 'cap': gen_caps[i]}

# Loads from Task 2-4 sheet (rows 3-7, cols 9-12)
# Col 9=name, 10=demand, 11=WTP (ignored in 2-4a), 12=location
df_load = pd.read_excel(file_path, sheet_name="Problem 2.4 - Loads", header=None)
n_loads = 5
load_demands = df_load.iloc[3:3+n_loads, 10].astype(float).tolist()
load_nodes   = [int(str(s).split()[-1]) for s in df_load.iloc[3:3+n_loads, 12]]

# Aggregate inflexible demand per node
demand = {}
for i in range(n_loads):
    n = load_nodes[i]
    demand[n] = demand.get(n, 0) + load_demands[i]

# Lines from Task 2-4 sheet (rows 3-5, cols 15-17)
line_cap_list  = df_load.iloc[3:6, 16].astype(float).tolist()
line_susc_list = df_load.iloc[3:6, 17].astype(float).tolist()
line_keys = []
for s in df_load.iloc[3:6, 15]:
    parts = str(s).split()[-1].split('-')
    line_keys.append((int(parts[0]), int(parts[1])))

susceptance   = dict(zip(line_keys, line_susc_list))
line_capacity = dict(zip(line_keys, line_cap_list))

nodes = sorted(demand.keys())
lines = sorted(line_keys)

# ==========================================================
# 2. Build and solve the DCOPF model
# ==========================================================

model = pyo.ConcreteModel("DCOPF_Task2_4a")

g_names = list(generators.keys())
model.N = pyo.Set(initialize=nodes)
model.G = pyo.Set(initialize=g_names)
model.L = pyo.Set(initialize=lines)

model.Pg    = pyo.Var(model.G, domain=pyo.NonNegativeReals)
model.theta = pyo.Var(model.N)
model.flow  = pyo.Var(model.L)

model.objective = pyo.Objective(
    expr=sum(generators[g]['cost'] * model.Pg[g] for g in model.G),
    sense=pyo.minimize)

def gen_rule(m, g):
    return m.Pg[g] <= generators[g]['cap']
model.gen_limit = pyo.Constraint(model.G, rule=gen_rule)

def flow_rule(m, i, j):
    return m.flow[i, j] == susceptance[(i, j)] * (m.theta[i] - m.theta[j])
model.flow_def = pyo.Constraint(model.L, rule=flow_rule)

def line_rule(m, i, j):
    return (-line_capacity[(i, j)], m.flow[i, j], line_capacity[(i, j)])
model.line_limit = pyo.Constraint(model.L, rule=line_rule)

def balance_rule(m, n):
    gen = sum(m.Pg[g] for g in model.G if generators[g]['node'] == n)
    out = sum(m.flow[i, j] for (i, j) in model.L if i == n)
    inp = sum(m.flow[i, j] for (i, j) in model.L if j == n)
    return gen - demand[n] == out - inp
model.balance = pyo.Constraint(model.N, rule=balance_rule)

model.theta[1].fix(0)
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

solver = pyo.SolverFactory("gurobi")
results = solver.solve(model)
assert results.solver.termination_condition == pyo.TerminationCondition.optimal

# ==========================================================
# 3. Print results
# ==========================================================

print("=" * 60)
print("  Task 2-4a: DCOPF — Multiple Loads at Node 2")
print("=" * 60)
print(f"\nTotal system cost: {pyo.value(model.objective):,.0f} NOK")
print(f"Demand: {demand}, total: {sum(demand.values()):.0f} MW")

print("\n--- Generator dispatch ---")
for g in g_names:
    pg = pyo.value(model.Pg[g])
    cap = generators[g]['cap']
    status = "At capacity" if pg >= cap - 0.01 \
        else ("Not dispatched" if pg < 0.01 else "Partial")
    print(f"  {g:8s} (Node {generators[g]['node']}, "
          f"{generators[g]['cost']:.0f} NOK/MWh): "
          f"{pg:8.2f} MW  [{status}]")

print("\n--- Nodal prices ---")
for n in nodes:
    print(f"  Node {n}: {model.dual[model.balance[n]]:8.2f} NOK/MWh")

print("\n--- Line flows ---")
for (i, j) in lines:
    f_val = pyo.value(model.flow[i, j])
    cap = line_capacity[(i, j)]
    binding = abs(abs(f_val) - cap) < 0.01
    print(f"  Line {i}-{j}: {f_val:8.2f} MW  (cap: {cap:.0f})"
          f"{'  ** BINDING **' if binding else ''}")

print("\n--- Shadow prices of binding constraints ---")
for g in g_names:
    d = model.dual[model.gen_limit[g]]
    if abs(d) > 1e-6:
        print(f"  {g} capacity: {d:.2f} NOK/MW")
for (i, j) in lines:
    d = model.dual[model.line_limit[(i, j)]]
    if abs(d) > 1e-6:
        print(f"  Line {i}-{j}: {d:.2f} NOK/MW")

# ==========================================================
# 4. Plot
# ==========================================================

fig, ax = plt.subplots(figsize=(8, 5))
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
    ax.bar(x, heights, bar_width, bottom=bottoms,
           color=colors[idx], edgecolor='white', linewidth=0.8)
    bottoms[n_idx] += pg
    label = g.replace('_', ',')
    patches.append(mpatches.Patch(
        color=colors[idx],
        label=f"{label} ({generators[g]['cost']:.0f} NOK/MWh, "
              f"cap {generators[g]['cap']:.0f} MW)"))

for i, n in enumerate(nodes):
    lam = model.dual[model.balance[n]]
    total_gen = sum(pyo.value(model.Pg[g])
                    for g in g_names if generators[g]['node'] == n)
    y_pos = max(total_gen, demand[n]) + 20
    ax.text(i, y_pos, f"\u03bb = {lam:.0f} NOK/MWh",
            ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.hlines([demand[n] for n in nodes], x - bar_width/2, x + bar_width/2,
          colors='black', linestyles='--', linewidth=1.5)
patches.append(plt.Line2D([0], [0], color='black', linestyle='--',
                           linewidth=1.5, label='Demand'))

ax.set_xticks(x)
ax.set_xticklabels([f'Node {n}' for n in nodes], fontsize=11)
ax.set_ylabel('Power [MW]', fontsize=11)
ax.set_title('Task 2-4a: Generation Dispatch\n(dashed line = nodal demand)',
             fontsize=12)
ax.legend(handles=patches, loc='upper right', fontsize=8)
ax.set_ylim(0, max(max(bottoms), max(demand.values())) * 1.25)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('task_2_4a_generation.png', dpi=150, bbox_inches='tight')
plt.show()
