#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TET4185 – Course Project (Spring 2026)
Problem 2.2: DC Optimal Power Flow and Flow-Based Market Coupling

This script solves:
  (a) DCOPF base case — cost minimisation with one generator per node
  (b) DCOPF with updated marginal cost at Node 3 (1000 NOK/MWh)
  (d) FBMC implementation using PTDFs, and comparison with DCOPF

Data is read from "Problem 2 data.xlsx", sheet "Problem 2.2 - Base case".
The susceptance values in the Excel file are the imaginary part of the
admittance (Y = G + jB), and are therefore negative. They are used directly
in the DC power flow equation: F_nm = B_nm * (theta_n - theta_m).
Per-unit base: 1000 MVA. Solver: Gurobi.
"""

# ==========================================================
# 1. Import libraries
# ==========================================================

import numpy as np
import pandas as pd
import pyomo.environ as pyo

# ==========================================================
# 2. Read system data from Excel
# ==========================================================

file_path = "Problem 2 data.xlsx"
sheet_name = "Problem 2.2 - Base case"

# Row layout: 0=section titles, 1=blank, 2=column headers, 3-5=data
df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

# Generators (col 0=name, 1=capacity, 2=cost, 3=location)
gen_cap_list   = df.iloc[3:6, 1].astype(int).tolist()    # [1000, 1000, 1000]
gen_cost_list  = df.iloc[3:6, 2].astype(int).tolist()    # [300, 1000, 600]

# Loads (col 9=name, 10=demand, 11=location)
load_demand_list = df.iloc[3:6, 10].astype(int).tolist()  # [200, 200, 500]

# Lines (col 15=name, 16=capacity, 17=susceptance)
line_cap_list  = df.iloc[3:6, 16].astype(int).tolist()    # [500, 500, 100]
line_susc_list = df.iloc[3:6, 17].astype(int).tolist()    # [-20, -10, -30]

# ==========================================================
# 3. Organise data into dictionaries
# ==========================================================

nodes      = [1, 2, 3]
generators = [1, 2, 3]
lines      = [(1, 2), (1, 3), (2, 3)]
ref_node   = 1
free_nodes = [n for n in nodes if n != ref_node]

gen_capacity  = dict(zip(generators, gen_cap_list))
demand        = dict(zip(nodes, load_demand_list))
susceptance   = dict(zip(lines, line_susc_list))   # negative, from Y-matrix
line_capacity = dict(zip(lines, line_cap_list))
gen_node      = {1: 1, 2: 2, 3: 3}

# Susceptance magnitudes (positive) for PTDF computation
b = {l: abs(susceptance[l]) for l in lines}


# ==========================================================
# 4. DCOPF model function (Tasks 2-2a and 2-2b)
# ==========================================================

def solve_dcopf(gen_cost, label=""):
    """Build and solve the DCOPF model with given generator costs."""

    m = pyo.ConcreteModel()
    m.N = pyo.Set(initialize=nodes)
    m.G = pyo.Set(initialize=generators)
    m.L = pyo.Set(initialize=lines)

    # Decision variables
    m.Pg    = pyo.Var(m.G, domain=pyo.NonNegativeReals)  # generator output [MW]
    m.theta = pyo.Var(m.N)                                # voltage angles
    m.flow  = pyo.Var(m.L)                                # line flows [MW]

    # Objective: minimise total generation cost
    m.objective = pyo.Objective(
        expr=sum(gen_cost[g] * m.Pg[g] for g in m.G),
        sense=pyo.minimize)

    # Generator capacity: 0 <= P_g <= P_g_max
    def gen_rule(m, g):
        return m.Pg[g] <= gen_capacity[g]
    m.gen_limit = pyo.Constraint(m.G, rule=gen_rule)

    # DC power flow: F_nm = B_nm * (theta_n - theta_m)
    def flow_rule(m, i, j):
        return m.flow[i, j] == susceptance[(i, j)] * (m.theta[i] - m.theta[j])
    m.flow_def = pyo.Constraint(m.L, rule=flow_rule)

    # Line capacity: -F_max <= F_nm <= F_max
    def line_rule(m, i, j):
        return (-line_capacity[(i, j)], m.flow[i, j], line_capacity[(i, j)])
    m.line_limit = pyo.Constraint(m.L, rule=line_rule)

    # Power balance at each bus (dual variable = nodal price lambda_n)
    def balance_rule(m, n):
        gen = sum(m.Pg[g] for g in m.G if gen_node[g] == n)
        out = sum(m.flow[i, j] for (i, j) in m.L if i == n)
        inp = sum(m.flow[i, j] for (i, j) in m.L if j == n)
        return gen - demand[n] == out - inp
    m.balance = pyo.Constraint(m.N, rule=balance_rule)

    # Reference bus: theta_1 = 0
    m.theta[ref_node].fix(0)

    # Enable dual variables (shadow prices)
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    # Solve
    solver = pyo.SolverFactory("gurobi")
    results = solver.solve(m)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    return m


def print_dcopf(m, gen_cost, label=""):
    """Print DCOPF results."""
    print("=" * 55)
    print(f"  DCOPF — {label}")
    print("=" * 55)
    print(f"\nTotal system cost: {pyo.value(m.objective):,.0f} NOK")

    print("\n--- Generator dispatch ---")
    for g in m.G:
        pg = pyo.value(m.Pg[g])
        status = "At capacity" if pg >= gen_capacity[g] - 0.01 \
            else ("Not dispatched" if pg < 0.01 else "Partial")
        print(f"  Gen {g} (Node {gen_node[g]}, {gen_cost[g]} NOK/MWh): "
              f"{pg:8.2f} MW  [{status}]")

    print("\n--- Nodal prices ---")
    for n in m.N:
        print(f"  Node {n}: {m.dual[m.balance[n]]:8.2f} NOK/MWh")

    print("\n--- Line flows ---")
    for (i, j) in m.L:
        f_val = pyo.value(m.flow[i, j])
        cap = line_capacity[(i, j)]
        binding = abs(abs(f_val) - cap) < 0.01
        print(f"  Line {i}-{j}: {f_val:8.2f} MW  (cap: {cap} MW)"
              f"{'  ** BINDING **' if binding else ''}")

    print("\n--- Shadow prices of binding constraints ---")
    for (i, j) in m.L:
        d = m.dual[m.line_limit[(i, j)]]
        if abs(d) > 1e-6:
            print(f"  Line {i}-{j}: {d:.2f} NOK/MW")
    for g in m.G:
        d = m.dual[m.gen_limit[g]]
        if abs(d) > 1e-6:
            print(f"  Gen {g} capacity: {d:.2f} NOK/MW")
    print()


# --- Task 2-2a: Base case ---
gen_cost_a = dict(zip(generators, gen_cost_list))
model_a = solve_dcopf(gen_cost_a)
print_dcopf(model_a, gen_cost_a, "Task 2-2a (Base Case)")

# --- Task 2-2b: Gen 3 cost = 1000 NOK/MWh ---
gen_cost_b = {1: 300, 2: 1000, 3: 1000}
model_b = solve_dcopf(gen_cost_b)
print_dcopf(model_b, gen_cost_b, "Task 2-2b (Gen 3 = 1000 NOK/MWh)")


# ==========================================================
# 5. Compute PTDF matrix (for Task 2-2d)
# ==========================================================
# PTDF = B_f_red * B_bus_red^{-1}
# B_bus_red: bus susceptance matrix with reference node removed
# B_f_red: branch-bus incidence matrix without reference column

B_bus = np.array([
    [ b[(1,2)] + b[(1,3)],  -b[(1,2)],              -b[(1,3)]],
    [-b[(1,2)],              b[(1,2)] + b[(2,3)],    -b[(2,3)]],
    [-b[(1,3)],             -b[(2,3)],                b[(1,3)] + b[(2,3)]]
])

B_bus_red     = B_bus[1:, 1:]
B_bus_red_inv = np.linalg.inv(B_bus_red)

# B_f: +b if from-node, -b if to-node
B_f_full = np.array([
    [+b[(1,2)], -b[(1,2)],          0],
    [+b[(1,3)],          0, -b[(1,3)]],
    [        0, +b[(2,3)], -b[(2,3)]]
])
B_f_red = B_f_full[:, 1:]  # remove reference column

PTDF_matrix = B_f_red @ B_bus_red_inv

print("=" * 55)
print("  PTDF Matrix (reference: Node 1)")
print("=" * 55)
print(f"{'Line':<12} {'Node 2':>10} {'Node 3':>10}")
for l_idx, (i, j) in enumerate(lines):
    print(f"Line {i}-{j:<6} {PTDF_matrix[l_idx, 0]:>10.4f} "
          f"{PTDF_matrix[l_idx, 1]:>10.4f}")

# Store as dictionary for FBMC model
PTDF = {}
for l_idx, l in enumerate(lines):
    PTDF[l] = {free_nodes[k]: PTDF_matrix[l_idx, k]
               for k in range(len(free_nodes))}


# ==========================================================
# 6. FBMC model (Task 2-2d)
# ==========================================================

def solve_fbmc(gen_cost, label=""):
    """Build and solve the FBMC model using PTDF-based flow constraints."""

    m = pyo.ConcreteModel()
    m.N = pyo.Set(initialize=nodes)
    m.L = pyo.Set(initialize=lines)

    # Generator output at each node [MW]
    m.Pg = pyo.Var(m.N, domain=pyo.NonNegativeReals)

    # Minimise total generation cost
    m.objective = pyo.Objective(
        expr=sum(gen_cost[n] * m.Pg[n] for n in m.N),
        sense=pyo.minimize)

    # Generator capacity
    def gen_rule(m, n):
        return m.Pg[n] <= gen_capacity[n]
    m.gen_limit = pyo.Constraint(m.N, rule=gen_rule)

    # Global power balance: total generation = total demand
    m.balance = pyo.Constraint(
        expr=sum(m.Pg[n] for n in m.N) == sum(demand.values()))

    # PTDF-based flow constraints:
    # -F_max <= sum_{n in free_nodes} PTDF_{l,n} * NP_n <= F_max
    # where NP_n = Pg_n - D_n (net position)
    def fbmc_rule(m, i, j):
        flow = sum(PTDF[(i, j)][n] * (m.Pg[n] - demand[n]) for n in free_nodes)
        return (-line_capacity[(i, j)], flow, line_capacity[(i, j)])
    m.flow_limit = pyo.Constraint(m.L, rule=fbmc_rule)

    # Enable duals
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    solver = pyo.SolverFactory("gurobi")
    results = solver.solve(m)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    return m


model_fbmc = solve_fbmc(gen_cost_a)

# --- Recover nodal prices from FBMC duals ---
lambda_sys = model_fbmc.dual[model_fbmc.balance]
mu = {l: model_fbmc.dual[model_fbmc.flow_limit[l]] for l in lines}

lambda_fbmc = {ref_node: lambda_sys}
for n in free_nodes:
    lambda_fbmc[n] = lambda_sys + sum(mu[l] * PTDF[l][n] for l in lines)

# --- Print FBMC results ---
print("\n" + "=" * 55)
print("  FBMC — Task 2-2d")
print("=" * 55)
print(f"\nTotal cost: {pyo.value(model_fbmc.objective):,.0f} NOK")
print("\n--- Dispatch ---")
for n in nodes:
    print(f"  Node {n}: {pyo.value(model_fbmc.Pg[n]):8.2f} MW")
print("\n--- Nodal prices ---")
for n in nodes:
    print(f"  Node {n}: {lambda_fbmc[n]:8.2f} NOK/MWh")

# --- Comparison table ---
print("\n" + "=" * 55)
print("  COMPARISON: DCOPF vs FBMC")
print("=" * 55)
print(f"\n{'':20} {'DCOPF':>10} {'FBMC':>10}")
for n in nodes:
    print(f"  P{n} [MW]            "
          f"{pyo.value(model_a.Pg[n]):>10.2f} {pyo.value(model_fbmc.Pg[n]):>10.2f}")
print(f"  Cost [NOK]          "
      f"{pyo.value(model_a.objective):>10.0f} {pyo.value(model_fbmc.objective):>10.0f}")
for n in nodes:
    print(f"  lambda_{n} [NOK/MWh]  "
          f"{model_a.dual[model_a.balance[n]]:>10.2f} {lambda_fbmc[n]:>10.2f}")
