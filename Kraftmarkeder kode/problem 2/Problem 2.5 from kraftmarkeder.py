#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TET4185 – Course Project (Spring 2026)
Problem 2.5: Environmental Constraints (CES and Cap-and-Trade)

Extends the social welfare maximization model from Task 2-4c with:
  A-C) A 20% Clean Energy Standard (CES)
  a-d) A cap-and-trade system (emission cap = CES emissions = 950 tonnes)

Both policies are compared to the no-policy baseline from Task 2-4c.

Data: "Problem 2 data.xlsx", sheet "Problem 2.5 - Environmental".
Note: This sheet has an extra CO2 column (col 4), which shifts the load
and line columns by one position compared to the other sheets.
Per-unit base: 1000 MVA. Solver: Gurobi.
"""

import numpy as np
import pandas as pd
import pyomo.environ as pyo

# ==========================================================
# 1. Read system data from Excel
# ==========================================================

file_path = "Problem 2 data.xlsx"
df = pd.read_excel(file_path, sheet_name="Problem 2.5 - Environmental", header=None)

# Generators: rows 3-7, cols 0-4
# Col 0=name, 1=capacity, 2=cost, 3=location, 4=CO2 [kg/MWh]
n_gens = 5
gen_names = df.iloc[3:3+n_gens, 0].tolist()
gen_caps  = df.iloc[3:3+n_gens, 1].astype(float).tolist()
gen_costs = df.iloc[3:3+n_gens, 2].astype(float).tolist()
gen_locs  = [int(str(s).split()[-1]) for s in df.iloc[3:3+n_gens, 3]]
gen_co2   = df.iloc[3:3+n_gens, 4].astype(float).tolist()

generators = {}
for i, name in enumerate(gen_names):
    generators[name] = {
        'node': gen_locs[i], 'cost': gen_costs[i],
        'cap': gen_caps[i], 'co2': gen_co2[i]
    }

# Loads: rows 3-7, cols 10-13
# Col 10=name, 11=demand, 12=WTP, 13=location
n_loads = 5
load_names_list = df.iloc[3:3+n_loads, 10].tolist()
load_demands    = df.iloc[3:3+n_loads, 11].astype(float).tolist()
load_wtp_raw    = df.iloc[3:3+n_loads, 12].tolist()
load_nodes      = [int(str(s).split()[-1]) for s in df.iloc[3:3+n_loads, 13]]

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

# Lines: rows 3-5, cols 17-19
# Col 17=name, 18=capacity, 19=susceptance
line_cap_list  = df.iloc[3:6, 18].astype(float).tolist()
line_susc_list = df.iloc[3:6, 19].astype(float).tolist()  # negative
line_keys = []
for s in df.iloc[3:6, 17]:
    parts = str(s).split()[-1].split('-')
    line_keys.append((int(parts[0]), int(parts[1])))

susceptance   = dict(zip(line_keys, line_susc_list))
line_capacity = dict(zip(line_keys, line_cap_list))

nodes = [1, 2, 3]
lines = sorted(line_keys)
g_names = list(generators.keys())

# Clean generators (zero CO2)
CES_ALPHA  = 0.20
clean_gens = [g for g in g_names if generators[g]['co2'] == 0]

# Print loaded data
print("=" * 60)
print("  Data — Problem 2.5")
print("=" * 60)
print(f"Clean generators: {clean_gens}")
for g in g_names:
    cln = " [CLEAN]" if g in clean_gens else ""
    print(f"  {g:8s}: {generators[g]['cost']:.0f} NOK/MWh, "
          f"cap={generators[g]['cap']:.0f} MW, "
          f"CO2={generators[g]['co2']:.0f} kg/MWh{cln}")


# ==========================================================
# 2. Reusable SW maximization model builder
# ==========================================================

def build_sw_model(add_ces=False, add_cap=None):
    """
    Social welfare maximization model (base: Task 2-4c).
    add_ces=True: adds 20% CES constraint.
    add_cap=value: adds emission cap constraint [kg].
    """
    m = pyo.ConcreteModel()
    m.N = pyo.Set(initialize=nodes)
    m.G = pyo.Set(initialize=g_names)
    m.L = pyo.Set(initialize=lines)

    m.Pg    = pyo.Var(m.G, domain=pyo.NonNegativeReals)
    m.Pd    = pyo.Var(load_names, domain=pyo.NonNegativeReals)
    m.theta = pyo.Var(m.N)
    m.flow  = pyo.Var(m.L)

    # Max SW = consumer utility - generation cost
    m.objective = pyo.Objective(
        expr=(sum(loads[l]['wtp'] * m.Pd[l] for l in flex_loads)
              - sum(generators[g]['cost'] * m.Pg[g] for g in m.G)),
        sense=pyo.maximize)

    # Inflexible loads
    def inflex_rule(m, l):
        return m.Pd[l] == loads[l]['demand']
    m.inflex_load = pyo.Constraint(inflex_loads, rule=inflex_rule)

    # Flexible load capacity
    def flex_rule(m, l):
        return m.Pd[l] <= loads[l]['demand']
    m.flex_cap = pyo.Constraint(flex_loads, rule=flex_rule)

    # Generator capacity
    def gen_rule(m, g):
        return m.Pg[g] <= generators[g]['cap']
    m.gen_limit = pyo.Constraint(m.G, rule=gen_rule)

    # DC power flow
    def flow_rule(m, i, j):
        return m.flow[i, j] == susceptance[(i, j)] * (m.theta[i] - m.theta[j])
    m.flow_def = pyo.Constraint(m.L, rule=flow_rule)

    # Line capacity
    def line_rule(m, i, j):
        return (-line_capacity[(i, j)], m.flow[i, j], line_capacity[(i, j)])
    m.line_limit = pyo.Constraint(m.L, rule=line_rule)

    # Power balance
    def balance_rule(m, n):
        gen  = sum(m.Pg[g] for g in m.G if generators[g]['node'] == n)
        load = sum(m.Pd[l] for l in load_names if loads[l]['node'] == n)
        out  = sum(m.flow[i, j] for (i, j) in m.L if i == n)
        inp  = sum(m.flow[i, j] for (i, j) in m.L if j == n)
        return gen - load == out - inp
    m.balance = pyo.Constraint(m.N, rule=balance_rule)

    m.theta[1].fix(0)

    # CES: clean generation >= alpha * total generation
    if add_ces:
        m.ces = pyo.Constraint(
            expr=sum(m.Pg[g] for g in clean_gens)
                 - CES_ALPHA * sum(m.Pg[g] for g in m.G) >= 0)

    # Emission cap: total CO2 <= cap [kg]
    if add_cap is not None:
        m.emission_cap = pyo.Constraint(
            expr=sum(generators[g]['co2'] * m.Pg[g] for g in m.G) <= add_cap)

    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    solver = pyo.SolverFactory("gurobi")
    results = solver.solve(m)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    return m


# ==========================================================
# 3. Extract and print results
# ==========================================================

def get_results(m, label=""):
    """Extract results from a solved model."""
    r = {'label': label}
    r['dispatch'] = {g: pyo.value(m.Pg[g]) for g in g_names}
    r['load_served'] = {l: pyo.value(m.Pd[l]) for l in load_names}
    r['prices'] = {n: -m.dual[m.balance[n]] for n in nodes}  # sign flip for max
    r['flows'] = {l: pyo.value(m.flow[l]) for l in lines}
    r['gen_cost'] = sum(generators[g]['cost'] * r['dispatch'][g] for g in g_names)
    r['utility'] = sum(loads[l]['wtp'] * r['load_served'][l] for l in flex_loads)
    r['sw'] = r['utility'] - r['gen_cost']
    r['co2'] = sum(generators[g]['co2'] * r['dispatch'][g] for g in g_names) / 1000
    r['total_gen'] = sum(r['dispatch'].values())
    if hasattr(m, 'ces'):
        r['kappa_ces'] = -m.dual[m.ces]
    if hasattr(m, 'emission_cap'):
        r['kappa_cap'] = -m.dual[m.emission_cap]
    return r


def print_results(r):
    print(f"\n{'='*60}")
    print(f"  {r['label']}")
    print(f"{'='*60}")
    print("\n--- Dispatch ---")
    for g in g_names:
        pg = r['dispatch'][g]
        status = "At cap" if pg >= generators[g]['cap'] - 0.01 \
            else ("Off" if pg < 0.01 else "Partial")
        print(f"  {g:8s}: {pg:8.2f} MW  [{status}]")
    print("\n--- Loads ---")
    for l in load_names:
        pd = r['load_served'][l]
        print(f"  {l:10s}: {pd:8.2f} MW  (max {loads[l]['demand']:.0f})")
    print(f"\n  Prices: {r['prices']}")
    print(f"  Gen cost:  {r['gen_cost']:>10,.0f} NOK")
    print(f"  Utility:   {r['utility']:>10,.0f} NOK")
    print(f"  SW:        {r['sw']:>10,.0f} NOK")
    print(f"  CO2:       {r['co2']:>10,.0f} tonnes")
    if 'kappa_ces' in r:
        print(f"  CES dual:  {r['kappa_ces']:.2f} NOK/MW")
    if 'kappa_cap' in r:
        print(f"  Cap dual:  {r['kappa_cap']:.4f} NOK/kg "
              f"= {r['kappa_cap']*1000:.2f} NOK/tonne")


# ==========================================================
# 4. Solve all scenarios
# ==========================================================

# Baseline (no policy)
m_base = build_sw_model()
r_base = get_results(m_base, "No policy (Task 2-4c baseline)")
print_results(r_base)

# 20% CES
m_ces = build_sw_model(add_ces=True)
r_ces = get_results(m_ces, "20% CES")
print_results(r_ces)

# Cap-and-trade (cap = CES emissions)
cap_kg = r_ces['co2'] * 1000  # 950 tonnes -> 950000 kg
m_cap = build_sw_model(add_cap=cap_kg)
r_cap = get_results(m_cap, f"Cap-and-trade (cap = {r_ces['co2']:.0f} tonnes)")
print_results(r_cap)


# ==========================================================
# 5. Full comparison table
# ==========================================================

print(f"\n{'='*60}")
print(f"  Comparison: No policy / CES / Cap-and-trade")
print(f"{'='*60}")
fmt = f"\n{'':24} {'No policy':>12} {'CES':>12} {'Cap-trade':>12}"
print(fmt)
for g in g_names:
    print(f"  {g:22s} {r_base['dispatch'][g]:>12.0f} "
          f"{r_ces['dispatch'][g]:>12.0f} {r_cap['dispatch'][g]:>12.0f}")
for l in flex_loads:
    print(f"  {l:22s} {r_base['load_served'][l]:>12.0f} "
          f"{r_ces['load_served'][l]:>12.0f} {r_cap['load_served'][l]:>12.0f}")
for (i,j) in lines:
    k = f"F{i}{j} [MW]"
    print(f"  {k:22s} {r_base['flows'][(i,j)]:>12.2f} "
          f"{r_ces['flows'][(i,j)]:>12.2f} {r_cap['flows'][(i,j)]:>12.2f}")
print(f"  {'lambda [NOK/MWh]':22s} {r_base['prices'][1]:>12.0f} "
      f"{r_ces['prices'][1]:>12.0f} {r_cap['prices'][1]:>12.0f}")
print(f"  {'Gen cost [NOK]':22s} {r_base['gen_cost']:>12,.0f} "
      f"{r_ces['gen_cost']:>12,.0f} {r_cap['gen_cost']:>12,.0f}")
print(f"  {'SW [NOK]':22s} {r_base['sw']:>12,.0f} "
      f"{r_ces['sw']:>12,.0f} {r_cap['sw']:>12,.0f}")
print(f"  {'CO2 [tonnes]':22s} {r_base['co2']:>12,.0f} "
      f"{r_ces['co2']:>12,.0f} {r_cap['co2']:>12,.0f}")
