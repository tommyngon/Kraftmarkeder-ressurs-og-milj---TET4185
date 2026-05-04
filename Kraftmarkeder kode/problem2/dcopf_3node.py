"""
dcopf_3node.py — Problem 2: DC Optimal Power Flow on 3-Node System
====================================================================
Solves the 3-node DC-OPF problem from TET4185 Problem 2.
Reads input data from Problem2_data.xlsx (same structure as Nordic Excel files).

Tasks covered
-------------
  2-2  Base DCOPF (FBMC / PTDF-based) — single generator per node
  2-3  Multiple generators per node (extended supply curve)
  2-4  Multiple loads per node (elastic demand, social welfare)
  2-5  Policy instruments: Carbon ETS and cap-and-trade comparison

The 3-node system has:
  Node 1: cheap hydro / gas generator, industrial load
  Node 2: mid-cost thermal generator, residential load
  Node 3: expensive peaker, mixed load
  Lines:  1-2, 1-3, 2-3  (all AC)

Run
---
    cd code/
    python problem2/dcopf_3node.py [task]

    where [task] is one of: all, 2-2, 2-3, 2-4, 2-5
    default: all
"""

import os
import sys
import numpy as np
import pandas as pd
import pyomo.environ as pyo

DATA_P2 = os.path.join(os.path.dirname(__file__), "../data/Problem2_data.xlsx")


# ===========================================================================
# Excel reader (same logic as nordic_base.py, adapted for 3-node file)
# ===========================================================================

def read_p2_excel(filename):
    """Read 3-node system data from Problem2_data.xlsx."""
    data = {}

    Excel_sheets = ["Node Parameters", "AC Branch Parameters", "DC Link Parameters"]
    Data_names   = {"Node Parameters": "Nodes",   "AC Branch Parameters": "AC-lines", "DC Link Parameters": "DC-lines"}
    Num_Names    = {"Node Parameters": "NumNodes", "AC Branch Parameters": "NumAC",    "DC Link Parameters": "NumDC"}
    List_Names   = {"Node Parameters": "NodeList", "AC Branch Parameters": "ACList",   "DC Link Parameters": "DCList"}

    for sheet in Excel_sheets:
        df  = pd.read_excel(filename, sheet_name=sheet, skiprows=1)
        df  = df.set_index(df.columns[0])
        num = len(df)
        df  = df.to_dict()
        df[Num_Names[sheet]]  = num
        df[List_Names[sheet]] = np.arange(1, num + 1)
        data[Data_names[sheet]] = df

    df = pd.read_excel(filename, sheet_name="Declarations", skiprows=1)
    df = df.set_index(df.columns[0]).to_dict()

    data["DCFlow"]         = bool(df["Value"][1])
    data["Reference node"] = int(df["Value"][2])
    data["ShedCost"]       = float(df["Value"][4])

    return data


# ===========================================================================
# Matrix construction (B, X)
# ===========================================================================

def build_matrices(data):
    N  = data["Nodes"]["NumNodes"]
    nL = data["AC-lines"]["NumAC"]
    nH = data["DC-lines"]["NumDC"]

    B = np.zeros((N, N))
    for l in range(1, nL + 1):
        fr = data["AC-lines"]["From"][l]
        to = data["AC-lines"]["To"][l]
        b  = data["AC-lines"]["Admittance"][l]
        B[fr-1, to-1] -= b; B[to-1, fr-1] -= b
        B[fr-1, fr-1] += b; B[to-1, to-1] += b
    data["B-matrix"] = B

    DC = np.zeros((nH, N))
    for h in range(1, nH + 1):
        DC[h-1, data["DC-lines"]["From"][h] - 1] =  1
        DC[h-1, data["DC-lines"]["To"][h]   - 1] = -1
    data["DC-matrix"] = DC

    X = np.zeros((nL, N))
    for l in range(1, nL + 1):
        X[l-1, data["AC-lines"]["From"][l] - 1] =  1
        X[l-1, data["AC-lines"]["To"][l]   - 1] = -1
    data["X-matrix"] = X

    return data


def build_ptdf(data):
    B   = data["B-matrix"]
    X   = data["X-matrix"]
    ref = data["Reference node"]
    N   = data["Nodes"]["NumNodes"]
    nL  = data["AC-lines"]["NumAC"]

    B_red     = np.delete(np.delete(B, ref-1, 0), ref-1, 1)
    B_red_inv = np.linalg.inv(B_red)

    b_vec  = np.array([data["AC-lines"]["Admittance"][l] for l in range(1, nL+1)])
    B_line = np.diag(b_vec)
    A_red  = np.delete(X, ref-1, axis=1)

    PTDF_red = B_line.dot(A_red).dot(B_red_inv)

    PTDF = np.zeros((nL, N))
    col  = 0
    for n in range(N):
        if n == ref - 1:
            PTDF[:, n] = 0.0
        else:
            PTDF[:, n] = PTDF_red[:, col]
            col += 1

    data["PTDF-matrix"] = PTDF
    return data


# ===========================================================================
# Task 2-2: Base DCOPF (FBMC and ATC)
# ===========================================================================

def task_2_2(data, verbose=True):
    """
    Solve the 3-node DCOPF using both FBMC (PTDF-based) and ATC (transport).
    Returns dict with results for both methods.
    """
    print("\n" + "=" * 60)
    print("  Task 2-2 — 3-Node DCOPF: FBMC vs ATC")
    print("=" * 60)

    results = {}

    for method, dcflow in [("FBMC", True), ("ATC", False)]:
        data["DCFlow"] = dcflow
        res = _solve_base(data, solver="gurobi")
        results[method] = res

        names = data["Nodes"]["NNAMES"]
        print(f"\n  --- {method} ---")
        print(f"  {'Node':<5} {'Name':<6} {'Demand':>8} {'Gen':>8} {'Shed':>8} {'Price':>10}")
        print(f"  {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
        for n in sorted(res["gen"]):
            print(f"  {n:<5} {names[n]:<6} {res['demand'][n]:>8.1f} {res['gen'][n]:>8.1f} "
                  f"{res['shed'][n]:>8.2f} {res['prices'][n]:>10.2f}")

        print(f"\n  AC line flows:")
        print(f"  {'Line':<5} {'From':>6} {'To':>6} {'Flow':>8} {'Cap+':>7} {'Cap-':>7}")
        print(f"  {'-'*5} {'-'*6} {'-'*6} {'-'*8} {'-'*7} {'-'*7}")
        for l in sorted(res["flow_ac"]):
            fr  = data["AC-lines"]["From"][l]
            to_ = data["AC-lines"]["To"][l]
            cap = data["AC-lines"]["Cap From"][l]
            cap2= data["AC-lines"]["Cap To"][l]
            print(f"  {l:<5} {names[fr]:>6} {names[to_]:>6} {res['flow_ac'][l]:>8.1f} "
                  f"{cap:>7.0f} {cap2:>7.0f}")

        print(f"\n  Objective: {res['objective']:,.2f} €/h")

        # Congestion rent
        total_cr = 0
        for l, fl in res["flow_ac"].items():
            fr  = data["AC-lines"]["From"][l]
            to_ = data["AC-lines"]["To"][l]
            cr  = fl * (res["prices"][to_] - res["prices"][fr])
            total_cr += cr
        print(f"  Total congestion rent: {total_cr:,.2f} €/h")

    return results


def _solve_base(data, solver="gurobi"):
    """Internal: solve FBMC or ATC depending on data['DCFlow']."""
    model = pyo.ConcreteModel()
    model.L = pyo.Set(ordered=True, initialize=data["AC-lines"]["ACList"])
    model.N = pyo.Set(ordered=True, initialize=data["Nodes"]["NodeList"])
    model.H = pyo.Set(ordered=True, initialize=data["DC-lines"]["DCList"])

    model.Demand    = pyo.Param(model.N, initialize=data["Nodes"]["DEMAND"])
    model.P_min     = pyo.Param(model.N, initialize=data["Nodes"]["GENMIN"])
    model.P_max     = pyo.Param(model.N, initialize=data["Nodes"]["GENCAP"])
    model.Cost_gen  = pyo.Param(model.N, initialize=data["Nodes"]["GENCOST"])
    model.Cost_shed = pyo.Param(initialize=data["ShedCost"])
    model.P_AC_max  = pyo.Param(model.L, initialize=data["AC-lines"]["Cap From"])
    model.P_AC_min  = pyo.Param(model.L, initialize=data["AC-lines"]["Cap To"])
    model.DC_cap    = pyo.Param(model.H, initialize=data["DC-lines"]["Cap"])

    model.gen        = pyo.Var(model.N, within=pyo.Reals)
    model.shed       = pyo.Var(model.N, within=pyo.NonNegativeReals)
    model.flow_AC    = pyo.Var(model.L, within=pyo.Reals)
    model.flow_DC    = pyo.Var(model.H, within=pyo.Reals)
    model.injections = pyo.Var(model.N, within=pyo.Reals)

    model.OBJ = pyo.Objective(
        expr=sum(model.gen[n]*model.Cost_gen[n] + model.shed[n]*model.Cost_shed
                 for n in model.N),
        sense=pyo.minimize)

    model.Min_gen_const       = pyo.Constraint(model.N, rule=lambda m, n: m.gen[n] >= m.P_min[n])
    model.Max_gen_const       = pyo.Constraint(model.N, rule=lambda m, n: m.gen[n] <= m.P_max[n])
    model.From_flow_L         = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
    model.To_flow_L           = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])
    model.FlowBalDC_max_const = pyo.Constraint(model.H, rule=lambda m, h: m.flow_DC[h] <=  m.DC_cap[h])
    model.FlowBalDC_min_const = pyo.Constraint(model.H, rule=lambda m, h: m.flow_DC[h] >= -m.DC_cap[h])

    if data["DCFlow"]:
        def InjDef(m, n):
            return m.injections[n] == (m.gen[n] - m.Demand[n] + m.shed[n]
                   - sum(data["DC-matrix"][h-1, n-1] * m.flow_DC[h] for h in m.H))
        model.InjDef_const = pyo.Constraint(model.N, rule=InjDef)

        def FlowBal(m, l):
            return m.flow_AC[l] == sum(data["PTDF-matrix"][l-1, n-1] * m.injections[n] for n in m.N)
        model.FlowBal_const = pyo.Constraint(model.L, rule=FlowBal)

        model.SystemBalance_const = pyo.Constraint(
            rule=lambda m: sum(m.injections[n] for n in m.N) == 0)
    else:
        def LoadBal(m, n):
            return (m.gen[n] + m.shed[n]
                    == m.Demand[n]
                    + sum(data["X-matrix"][l-1, n-1]  * m.flow_AC[l] for l in m.L)
                    + sum(data["DC-matrix"][h-1, n-1] * m.flow_DC[h] for h in m.H))
        model.LoadBal_const = pyo.Constraint(model.N, rule=LoadBal)

    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    opt = pyo.SolverFactory("gurobi")
    opt.solve(model, load_solutions=True)

    if data["DCFlow"]:
        prices = {n: model.dual[model.InjDef_const[n]]  for n in model.N}
    else:
        prices = {n: model.dual[model.LoadBal_const[n]] for n in model.N}

    return {
        "objective": model.OBJ(),
        "gen":       {n: model.gen[n].value     for n in model.N},
        "shed":      {n: model.shed[n].value     for n in model.N},
        "prices":    prices,
        "flow_ac":   {l: model.flow_AC[l].value  for l in model.L},
        "flow_dc":   {h: model.flow_DC[h].value  for h in model.H},
        "demand":    {n: model.Demand[n]          for n in model.N},
    }


# ===========================================================================
# Task 2-3: Multiple Generators — extended supply stack
# ===========================================================================

def task_2_3(data, verbose=True):
    """
    Extend Task 2-2 to allow each node to have multiple generators (supply steps).
    Generators are indexed by (node, unit) pairs.

    This demonstrates the merit-order dispatch within each bidding zone.
    The model selects the cheapest generator combination subject to line limits.
    """
    print("\n" + "=" * 60)
    print("  Task 2-3 — Multiple Generators per Node")
    print("=" * 60)

    # Extended supply curve: {(node, unit): (cap_MW, cost_€/MWh)}
    # These are illustrative supply steps consistent with the 3-node report data
    GENERATORS = {
        (1, 1): (200, 10),   # Node 1, cheap hydro
        (1, 2): (150, 25),   # Node 1, mid thermal
        (2, 1): (100, 30),   # Node 2, base thermal
        (2, 2): (200, 45),   # Node 2, gas
        (3, 1): (150, 50),   # Node 3, gas peaker
        (3, 2): ( 80, 70),   # Node 3, oil peaker
    }

    DEMAND   = dict(data["Nodes"]["DEMAND"])    # {n: MW}
    SHED_COST = data["ShedCost"]

    # Build sets
    GEN_UNITS = list(GENERATORS.keys())         # [(n, u)]
    NODES     = list(data["Nodes"]["NodeList"])
    LINES     = list(data["AC-lines"]["ACList"])

    model = pyo.ConcreteModel()
    model.G = pyo.Set(ordered=True, initialize=GEN_UNITS, dimen=2)
    model.N = pyo.Set(ordered=True, initialize=NODES)
    model.L = pyo.Set(ordered=True, initialize=LINES)

    model.Cap    = pyo.Param(model.G, initialize={k: v[0] for k, v in GENERATORS.items()})
    model.Cost   = pyo.Param(model.G, initialize={k: v[1] for k, v in GENERATORS.items()})
    model.Demand = pyo.Param(model.N, initialize=DEMAND)

    model.P_AC_max = pyo.Param(model.L, initialize=data["AC-lines"]["Cap From"])
    model.P_AC_min = pyo.Param(model.L, initialize=data["AC-lines"]["Cap To"])

    model.gen     = pyo.Var(model.G, within=pyo.NonNegativeReals)
    model.shed    = pyo.Var(model.N, within=pyo.NonNegativeReals)
    model.flow_AC = pyo.Var(model.L, within=pyo.Reals)
    model.inj     = pyo.Var(model.N, within=pyo.Reals)

    # Objective: minimise total generation + shedding cost
    model.OBJ = pyo.Objective(
        expr=(sum(model.gen[n, u] * model.Cost[n, u] for (n, u) in GEN_UNITS) +
              sum(model.shed[n] * SHED_COST             for n in NODES)),
        sense=pyo.minimize)

    # Generation capacity bounds
    def cap_ub(m, n, u):
        return m.gen[n, u] <= m.Cap[n, u]
    model.cap_const = pyo.Constraint(model.G, rule=cap_ub)

    # Injection definition (FBMC): inj = total_gen - demand + shed
    def inj_def(m, n):
        gen_n = sum(m.gen[n, u] for (nn, u) in GEN_UNITS if nn == n)
        return m.inj[n] == gen_n - m.Demand[n] + m.shed[n]
    model.inj_const = pyo.Constraint(model.N, rule=inj_def)

    # PTDF flow balance
    def flow_bal(m, l):
        return m.flow_AC[l] == sum(data["PTDF-matrix"][l-1, n-1] * m.inj[n] for n in NODES)
    model.flow_bal_const = pyo.Constraint(model.L, rule=flow_bal)

    # System balance
    model.sys_bal = pyo.Constraint(rule=lambda m: sum(m.inj[n] for n in NODES) == 0)

    # Line limits
    model.line_ub = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
    model.line_lb = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])

    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    pyo.SolverFactory("gurobi").solve(model, load_solutions=True)

    prices = {n: model.dual[model.inj_const[n]] for n in NODES}

    print(f"\n  Generator dispatch:")
    print(f"  {'(n,u)':<8} {'Cap':>6} {'Cost':>6} {'Dispatch':>9} {'Utilization':>12}")
    print(f"  {'-'*8} {'-'*6} {'-'*6} {'-'*9} {'-'*12}")
    for (n, u) in GEN_UNITS:
        g   = model.gen[n, u].value
        cap = GENERATORS[(n, u)][0]
        c   = GENERATORS[(n, u)][1]
        print(f"  ({n},{u})    {cap:>6.0f} {c:>6.0f} {g:>9.2f} {g/cap*100:>11.1f}%")

    names = data["Nodes"]["NNAMES"]
    print(f"\n  Nodal summary:")
    print(f"  {'Node':<5} {'Name':<6} {'Demand':>8} {'Gen':>8} {'Shed':>8} {'Price':>10}")
    print(f"  {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
    for n in NODES:
        gen_n = sum(model.gen[n, u].value for (nn, u) in GEN_UNITS if nn == n)
        print(f"  {n:<5} {names[n]:<6} {DEMAND[n]:>8.1f} {gen_n:>8.1f} "
              f"{model.shed[n].value:>8.2f} {prices[n]:>10.2f}")

    print(f"\n  Objective: {model.OBJ():,.2f} €/h")
    return {"objective": model.OBJ(), "prices": prices}


# ===========================================================================
# Task 2-4: Multiple Loads / Elastic Demand — Social Welfare Maximisation
# ===========================================================================

def task_2_4(data, verbose=True):
    """
    Model elastic demand (downward-sloping) and maximise social welfare:
        SW = consumer surplus + producer surplus
           = sum(WTP[n]*load[n]) - sum(cost[n]*gen[n])

    Each node has a step-wise demand function: high-WTP consumers served first.
    """
    print("\n" + "=" * 60)
    print("  Task 2-4 — Multiple Loads (Elastic Demand) — Social Welfare")
    print("=" * 60)

    # Step-wise demand (WTP = willingness-to-pay):  {(node, step): (MW, €/MWh)}
    LOADS = {
        (1, 1): (100, 80),   # High-WTP industrial
        (1, 2): (150, 55),   # Residential
        (1, 3): ( 80, 30),   # Low-priority
        (2, 1): ( 80, 90),
        (2, 2): (120, 60),
        (2, 3): (100, 35),
        (3, 1): ( 60, 75),
        (3, 2): (100, 50),
        (3, 3): ( 90, 20),
    }

    # Generators (same as Task 2-3)
    GENERATORS = {
        (1, 1): (200, 10),
        (1, 2): (150, 25),
        (2, 1): (100, 30),
        (2, 2): (200, 45),
        (3, 1): (150, 50),
        (3, 2): ( 80, 70),
    }

    NODES = list(data["Nodes"]["NodeList"])
    LINES = list(data["AC-lines"]["ACList"])
    GEN_UNITS  = list(GENERATORS.keys())
    LOAD_STEPS = list(LOADS.keys())

    model = pyo.ConcreteModel()
    model.G = pyo.Set(ordered=True, initialize=GEN_UNITS,  dimen=2)
    model.D = pyo.Set(ordered=True, initialize=LOAD_STEPS, dimen=2)
    model.N = pyo.Set(ordered=True, initialize=NODES)
    model.L = pyo.Set(ordered=True, initialize=LINES)

    model.Cap_gen  = pyo.Param(model.G, initialize={k: v[0] for k, v in GENERATORS.items()})
    model.Cost_gen = pyo.Param(model.G, initialize={k: v[1] for k, v in GENERATORS.items()})
    model.Cap_load = pyo.Param(model.D, initialize={k: v[0] for k, v in LOADS.items()})
    model.WTP      = pyo.Param(model.D, initialize={k: v[1] for k, v in LOADS.items()})

    model.P_AC_max = pyo.Param(model.L, initialize=data["AC-lines"]["Cap From"])
    model.P_AC_min = pyo.Param(model.L, initialize=data["AC-lines"]["Cap To"])

    model.gen     = pyo.Var(model.G, within=pyo.NonNegativeReals)
    model.load    = pyo.Var(model.D, within=pyo.NonNegativeReals)
    model.flow_AC = pyo.Var(model.L, within=pyo.Reals)
    model.inj     = pyo.Var(model.N, within=pyo.Reals)

    # Objective: maximise social welfare = revenues (WTP) - generation cost
    model.OBJ = pyo.Objective(
        expr=(sum(model.load[n, s] * model.WTP[n, s]  for (n, s) in LOAD_STEPS) -
              sum(model.gen[n, u]  * model.Cost_gen[n, u] for (n, u) in GEN_UNITS)),
        sense=pyo.maximize)

    # Bounds
    model.gen_ub  = pyo.Constraint(model.G, rule=lambda m, n, u: m.gen[n, u]  <= m.Cap_gen[n, u])
    model.load_ub = pyo.Constraint(model.D, rule=lambda m, n, s: m.load[n, s] <= m.Cap_load[n, s])

    # Injection = net export
    def inj_def(m, n):
        gen_n  = sum(m.gen[n, u]  for (nn, u) in GEN_UNITS  if nn == n)
        load_n = sum(m.load[n, s] for (nn, s) in LOAD_STEPS if nn == n)
        return m.inj[n] == gen_n - load_n
    model.inj_const = pyo.Constraint(model.N, rule=inj_def)

    def flow_bal(m, l):
        return m.flow_AC[l] == sum(data["PTDF-matrix"][l-1, n-1] * m.inj[n] for n in NODES)
    model.flow_bal_const = pyo.Constraint(model.L, rule=flow_bal)

    model.sys_bal = pyo.Constraint(rule=lambda m: sum(m.inj[n] for n in NODES) == 0)
    model.line_ub = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
    model.line_lb = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])

    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    pyo.SolverFactory("gurobi").solve(model, load_solutions=True)

    prices = {n: model.dual[model.inj_const[n]] for n in NODES}
    names  = data["Nodes"]["NNAMES"]

    print(f"\n  Social Welfare: {model.OBJ():,.2f} €/h")
    print(f"\n  Nodal prices: " + "  ".join(f"{names[n]}: {prices[n]:.2f}" for n in NODES))

    total_gen  = sum(model.gen[k].value  for k in GEN_UNITS)
    total_load = sum(model.load[k].value for k in LOAD_STEPS)
    print(f"  Total generation: {total_gen:.1f} MW  |  Total consumption: {total_load:.1f} MW")

    print(f"\n  Demand served per step:")
    print(f"  {'(n,s)':<8} {'Cap':>6} {'WTP':>6} {'Served':>8} {'Util%':>7}")
    print(f"  {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*7}")
    for (n, s) in LOAD_STEPS:
        sv  = model.load[n, s].value
        cap = LOADS[(n, s)][0]
        wtp = LOADS[(n, s)][1]
        print(f"  ({n},{s})    {cap:>6.0f} {wtp:>6.0f} {sv:>8.2f} {sv/cap*100:>6.1f}%")

    return {"objective": model.OBJ(), "prices": prices}


# ===========================================================================
# Task 2-5: Policy Instruments — Carbon ETS and Cap-and-Trade
# ===========================================================================

def task_2_5(data, verbose=True):
    """
    Compare two carbon policy instruments on the 3-node system:

    (a) Carbon price / ETS:
        Adds emission intensity × carbon price to each generator's cost.
        Carbon price set exogenously.

    (b) Cap-and-trade:
        Imposes a total CO₂ cap across all generators.
        The shadow price of the cap constraint = endogenous CO₂ price.
        This is equivalent to a cap-and-trade system at equilibrium.
    """
    print("\n" + "=" * 60)
    print("  Task 2-5 — Carbon Policy: ETS vs Cap-and-Trade")
    print("=" * 60)

    # Generator data with emission intensities [tCO₂/MWh]
    # {(node, unit): (cap_MW, base_cost_€/MWh, intensity_tCO2/MWh)}
    GENERATORS = {
        (1, 1): (200, 10, 0.02),   # Hydro (low emissions)
        (1, 2): (150, 25, 0.40),   # Gas
        (2, 1): (100, 30, 0.50),   # Coal
        (2, 2): (200, 45, 0.45),   # Gas CC
        (3, 1): (150, 50, 0.60),   # Gas peaker
        (3, 2): ( 80, 70, 0.80),   # Oil peaker
    }

    DEMAND   = dict(data["Nodes"]["DEMAND"])
    SHED_COST = data["ShedCost"]
    NODES    = list(data["Nodes"]["NodeList"])
    LINES    = list(data["AC-lines"]["ACList"])
    GEN_KEYS = list(GENERATORS.keys())

    # Total baseline emissions (no policy)
    # We first solve without any carbon price to get baseline
    def solve_with_carbon_price(p_co2):
        model = pyo.ConcreteModel()
        model.G = pyo.Set(ordered=True, initialize=GEN_KEYS, dimen=2)
        model.N = pyo.Set(ordered=True, initialize=NODES)
        model.L = pyo.Set(ordered=True, initialize=LINES)

        model.Cap  = pyo.Param(model.G, initialize={k: v[0] for k, v in GENERATORS.items()})
        model.Cost = pyo.Param(model.G, initialize={
            k: v[1] + v[2] * p_co2 for k, v in GENERATORS.items()})   # Add CO₂ adder
        model.Dem  = pyo.Param(model.N, initialize=DEMAND)
        model.P_AC_max = pyo.Param(model.L, initialize=data["AC-lines"]["Cap From"])
        model.P_AC_min = pyo.Param(model.L, initialize=data["AC-lines"]["Cap To"])

        model.gen     = pyo.Var(model.G, within=pyo.NonNegativeReals)
        model.shed    = pyo.Var(model.N, within=pyo.NonNegativeReals)
        model.flow_AC = pyo.Var(model.L, within=pyo.Reals)
        model.inj     = pyo.Var(model.N, within=pyo.Reals)

        model.OBJ = pyo.Objective(
            expr=sum(model.gen[k]*model.Cost[k] for k in GEN_KEYS) +
                 sum(model.shed[n]*SHED_COST for n in NODES),
            sense=pyo.minimize)

        model.cap_c   = pyo.Constraint(model.G, rule=lambda m, n, u: m.gen[n, u] <= m.Cap[n, u])
        model.inj_def = pyo.Constraint(model.N, rule=lambda m, n:
            m.inj[n] == sum(m.gen[n, u] for (nn, u) in GEN_KEYS if nn == n) - m.Dem[n] + m.shed[n])
        model.flow_b  = pyo.Constraint(model.L, rule=lambda m, l:
            m.flow_AC[l] == sum(data["PTDF-matrix"][l-1, n-1]*m.inj[n] for n in NODES))
        model.sys_b   = pyo.Constraint(rule=lambda m: sum(m.inj[n] for n in NODES) == 0)
        model.line_ub = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
        model.line_lb = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])

        model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        pyo.SolverFactory("gurobi").solve(model, load_solutions=True)

        total_em = sum(model.gen[k].value * GENERATORS[k][2] for k in GEN_KEYS)
        prices   = {n: model.dual[model.inj_def[n]] for n in NODES}
        return model.OBJ(), total_em, prices, {k: model.gen[k].value for k in GEN_KEYS}

    # (a) ETS: sweep over carbon prices
    co2_prices = [0, 20, 40, 60, 80]
    print(f"\n  (a) Carbon ETS — sensitivity to p_CO2:")
    print(f"  {'p_CO2':>7} {'Cost [€/h]':>12} {'Emissions [tCO₂/h]':>20}")
    print(f"  {'-'*7} {'-'*12} {'-'*20}")
    baseline_em = None
    ets_results = {}
    for p in co2_prices:
        cost, em, prices, gen = solve_with_carbon_price(p)
        if baseline_em is None:
            baseline_em = em
        ets_results[p] = {"cost": cost, "em": em, "prices": prices, "gen": gen}
        print(f"  {p:>7} {cost:>12,.2f} {em:>20.2f}")

    # (b) Cap-and-trade: fix emissions to 80% of baseline, find shadow price
    cap_em = 0.8 * baseline_em

    model = pyo.ConcreteModel()
    model.G = pyo.Set(ordered=True, initialize=GEN_KEYS, dimen=2)
    model.N = pyo.Set(ordered=True, initialize=NODES)
    model.L = pyo.Set(ordered=True, initialize=LINES)

    model.Cap  = pyo.Param(model.G, initialize={k: v[0] for k, v in GENERATORS.items()})
    model.Cost = pyo.Param(model.G, initialize={k: v[1] for k, v in GENERATORS.items()})  # NO carbon adder
    model.Dem  = pyo.Param(model.N, initialize=DEMAND)
    model.P_AC_max = pyo.Param(model.L, initialize=data["AC-lines"]["Cap From"])
    model.P_AC_min = pyo.Param(model.L, initialize=data["AC-lines"]["Cap To"])

    model.gen     = pyo.Var(model.G, within=pyo.NonNegativeReals)
    model.shed    = pyo.Var(model.N, within=pyo.NonNegativeReals)
    model.flow_AC = pyo.Var(model.L, within=pyo.Reals)
    model.inj     = pyo.Var(model.N, within=pyo.Reals)

    model.OBJ = pyo.Objective(
        expr=sum(model.gen[k]*model.Cost[k] for k in GEN_KEYS) +
             sum(model.shed[n]*SHED_COST for n in NODES),
        sense=pyo.minimize)

    model.cap_c   = pyo.Constraint(model.G, rule=lambda m, n, u: m.gen[n, u] <= m.Cap[n, u])
    model.inj_def = pyo.Constraint(model.N, rule=lambda m, n:
        m.inj[n] == sum(m.gen[n, u] for (nn, u) in GEN_KEYS if nn == n) - m.Dem[n] + m.shed[n])
    model.flow_b  = pyo.Constraint(model.L, rule=lambda m, l:
        m.flow_AC[l] == sum(data["PTDF-matrix"][l-1, n-1]*m.inj[n] for n in NODES))
    model.sys_b   = pyo.Constraint(rule=lambda m: sum(m.inj[n] for n in NODES) == 0)
    model.line_ub = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
    model.line_lb = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])

    # THE cap-and-trade constraint: total emissions ≤ cap
    model.em_cap  = pyo.Constraint(
        rule=lambda m: sum(m.gen[k] * GENERATORS[k][2] for k in GEN_KEYS) <= cap_em)

    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    pyo.SolverFactory("gurobi").solve(model, load_solutions=True)

    endogenous_co2_price = model.dual[model.em_cap]
    total_em_cap = sum(model.gen[k].value * GENERATORS[k][2] for k in GEN_KEYS)

    print(f"\n  (b) Cap-and-Trade:")
    print(f"      Baseline emissions:  {baseline_em:.2f} tCO₂/h")
    print(f"      Emissions cap (80%): {cap_em:.2f} tCO₂/h")
    print(f"      Actual emissions:    {total_em_cap:.2f} tCO₂/h")
    print(f"      Endogenous CO₂ price (dual of cap): {endogenous_co2_price:.2f} €/tCO₂")
    print(f"      System cost:         {model.OBJ():,.2f} €/h  (excl. permit revenue)")

    print(f"\n  Summary: ETS vs Cap-and-Trade at equivalent emission level")
    print(f"  {'Method':<25} {'p_CO2':>8} {'Emissions':>10} {'Cost':>12}")
    print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*12}")
    # Find closest ETS price to achieve same emission reduction
    for p in co2_prices:
        em = ets_results[p]["em"]
        if abs(em - cap_em) == min(abs(ets_results[pp]["em"] - cap_em) for pp in co2_prices):
            print(f"  {'ETS (closest equiv.)':<25} {p:>8} {em:>10.2f} {ets_results[p]['cost']:>12,.2f}")
    print(f"  {'Cap-and-Trade':<25} {endogenous_co2_price:>8.2f} {total_em_cap:>10.2f} {model.OBJ():>12,.2f}")

    return {
        "ets_results": ets_results,
        "cap_trade_co2_price": endogenous_co2_price,
        "cap_trade_emissions": total_em_cap,
    }


# ===========================================================================
# Main dispatcher
# ===========================================================================

def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("\n" + "=" * 60)
    print("  Problem 2 — 3-Node DC-OPF")
    print(f"  Data file: {DATA_P2}")
    print("=" * 60)

    # Load and prepare data
    data = read_p2_excel(DATA_P2)
    data = build_matrices(data)
    data = build_ptdf(data)

    if task in ("all", "2-2"):
        task_2_2(data)

    if task in ("all", "2-3"):
        task_2_3(data)

    if task in ("all", "2-4"):
        task_2_4(data)

    if task in ("all", "2-5"):
        task_2_5(data)

    print("\n\nDone.")


if __name__ == "__main__":
    main()
