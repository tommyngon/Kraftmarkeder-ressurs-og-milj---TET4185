"""
nordic_base.py
==============
Shared solver module for the Nordic 12-node power market model.

This is a refactored version of the course-provided "FBMC Pyomo script.py".
All task scripts in problem3/ and problem4/ import and call solve_nordic().

Nordic nodes (1-indexed, matching Excel):
  1  NO4   2  NO3   3  NO5   4  NO2   5  NO1
  6  SE1*  7  SE2   8  SE3   9  SE4  10  FI
 11  DK1  12  DK2
  (* SE1 is the reference node, theta = 0)

Usage
-----
    from nordic_base import solve_nordic

    # FBMC (DC power flow), wet year
    res = solve_nordic("../data/Nordic_wet.xlsx", dcflow=True)

    # ATC (transport network), with generation cap override
    res = solve_nordic("../data/Nordic_wet.xlsx", dcflow=False,
                       gencap_override={8: 4000})

Returns
-------
A dict with keys:
    objective      float   Total system cost [€]
    gen            dict    {n: MW}   generation per node
    shed           dict    {n: MW}   load shedding per node
    prices         dict    {n: €/MWh}  nodal prices (dual of balance)
    flow_ac        dict    {l: MW}   AC line flows
    flow_dc        dict    {h: MW}   DC link flows
    shadow_ac      dict    {l: €/MWh} line shadow price (FBMC dual of FlowBal)
    shadow_ac_ub   dict    {l: €/MWh} upper bound dual  (ATC From_flow_L)
    shadow_ac_lb   dict    {l: €/MWh} lower bound dual  (ATC To_flow_L)
    demand         dict    {n: MW}   demand per node (after any override)
    node_names     dict    {n: str}  node names from Excel
    dcflow         bool    True=FBMC, False=ATC
    Data           dict    full parsed + matrix data (for ad-hoc inspection)
"""

import sys
import numpy as np
import pandas as pd
import pyomo.environ as pyo


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def solve_nordic(
    filename,
    dcflow=None,               # override Excel DCFlow flag (True=FBMC, False=ATC)
    demand_override=None,      # dict {node_id: new_demand_MW}
    gencap_override=None,      # dict {node_id: new_cap_MW}
    cost_override=None,        # dict {node_id: new_cost_€/MWh}
    solver="gurobi",
    verbose=False,
):
    """
    Read Excel data, build and solve the FBMC or ATC model, return results dict.

    Parameters
    ----------
    filename        : str   Path to Nordic Excel file (e.g. '../data/Nordic_wet.xlsx')
    dcflow          : bool  True = FBMC (PTDF-based DCOPF), False = ATC transport model.
                            If None, reads the flag from the Excel Declarations sheet.
    demand_override : dict  {node_id (1-indexed): demand_MW}  — replaces DEMAND values.
    gencap_override : dict  {node_id (1-indexed): cap_MW}     — replaces GENCAP values.
    cost_override   : dict  {node_id (1-indexed): cost_€/MWh} — replaces GENCOST values.
    solver          : str   Pyomo solver name (default 'gurobi').
    verbose         : bool  If True, print solver output and summary.
    """
    Data = _read_excel(filename)

    # Override DCFlow flag if caller specifies it
    if dcflow is not None:
        Data["DCFlow"] = bool(dcflow)

    # Validate
    if Data["Reference node"] <= 0 or Data["Reference node"] > Data["Nodes"]["NumNodes"]:
        raise ValueError("Invalid reference node in Excel Declarations sheet.")
    if Data["DCFlow"] not in (True, False):
        raise ValueError("DCFlow must be 0 or 1 in Declarations sheet.")

    # Apply overrides
    if demand_override:
        for n, val in demand_override.items():
            Data["Nodes"]["DEMAND"][n] = val
    if gencap_override:
        for n, val in gencap_override.items():
            Data["Nodes"]["GENCAP"][n] = val
    if cost_override:
        for n, val in cost_override.items():
            Data["Nodes"]["GENCOST"][n] = val

    Data = _create_matrices(Data)
    Data = _calculate_ptdf(Data)

    results = _run_model(Data, solver=solver, verbose=verbose)
    return results


# ---------------------------------------------------------------------------
# Excel reader
# ---------------------------------------------------------------------------

def _read_excel(name):
    data = {}

    Excel_sheets = ["Node Parameters", "AC Branch Parameters", "DC Link Parameters"]
    Data_names   = {"Node Parameters": "Nodes",    "AC Branch Parameters": "AC-lines",  "DC Link Parameters": "DC-lines"}
    Num_Names    = {"Node Parameters": "NumNodes",  "AC Branch Parameters": "NumAC",     "DC Link Parameters": "NumDC"}
    List_Names   = {"Node Parameters": "NodeList",  "AC Branch Parameters": "ACList",    "DC Link Parameters": "DCList"}

    for sheet in Excel_sheets:
        df  = pd.read_excel(name, sheet_name=sheet, skiprows=1)
        df  = df.set_index(df.columns[0])
        num = len(df)
        df  = df.to_dict()
        df[Num_Names[sheet]]  = num
        df[List_Names[sheet]] = np.arange(1, num + 1)
        data[Data_names[sheet]] = df

    df = pd.read_excel(name, sheet_name="Declarations", skiprows=1)
    df = df.set_index(df.columns[0]).to_dict()

    data["DCFlow"]         = bool(df["Value"][1])   # 1 → FBMC, 0 → ATC
    data["Reference node"] = int(df["Value"][2])
    data["ShedCost"]       = float(df["Value"][4])

    return data


# ---------------------------------------------------------------------------
# Matrix construction (B, DC-incidence, X-incidence)
# ---------------------------------------------------------------------------

def _create_matrices(Data):
    N  = Data["Nodes"]["NumNodes"]
    nL = Data["AC-lines"]["NumAC"]
    nH = Data["DC-lines"]["NumDC"]

    # Nodal susceptance (B) matrix  [N x N]
    B = np.zeros((N, N))
    for l in range(1, nL + 1):
        fr = Data["AC-lines"]["From"][l]
        to = Data["AC-lines"]["To"][l]
        b  = Data["AC-lines"]["Admittance"][l]
        B[fr-1, to-1] -= b
        B[to-1, fr-1] -= b
        B[fr-1, fr-1] += b
        B[to-1, to-1] += b
    Data["B-matrix"] = B

    # DC incidence matrix [nH x N]  (+1 from-node, -1 to-node)
    DC = np.zeros((nH, N))
    for h in range(1, nH + 1):
        DC[h-1, Data["DC-lines"]["From"][h] - 1] =  1
        DC[h-1, Data["DC-lines"]["To"][h]   - 1] = -1
    Data["DC-matrix"] = DC

    # AC incidence matrix [nL x N]  (+1 from-node, -1 to-node)
    X = np.zeros((nL, N))
    for l in range(1, nL + 1):
        X[l-1, Data["AC-lines"]["From"][l] - 1] =  1
        X[l-1, Data["AC-lines"]["To"][l]   - 1] = -1
    Data["X-matrix"] = X

    return Data


# ---------------------------------------------------------------------------
# PTDF matrix  H = B_line · A_reduced · B_reduced⁻¹
# ---------------------------------------------------------------------------

def _calculate_ptdf(Data):
    B       = Data["B-matrix"]
    X       = Data["X-matrix"]
    ref     = Data["Reference node"]   # 1-indexed
    N       = Data["Nodes"]["NumNodes"]
    nL      = Data["AC-lines"]["NumAC"]

    # Remove reference row/col from B
    B_red     = np.delete(np.delete(B, ref-1, axis=0), ref-1, axis=1)
    B_red_inv = np.linalg.inv(B_red)

    # Line susceptance diagonal
    b_vec  = np.array([Data["AC-lines"]["Admittance"][l] for l in range(1, nL+1)])
    B_line = np.diag(b_vec)

    # Reduced incidence (remove ref column)
    A_red  = np.delete(X, ref-1, axis=1)

    PTDF_red = B_line.dot(A_red).dot(B_red_inv)

    # Re-insert reference column (zeros)
    PTDF = np.zeros((nL, N))
    col  = 0
    for n in range(N):
        if n == ref - 1:
            PTDF[:, n] = 0.0
        else:
            PTDF[:, n] = PTDF_red[:, col]
            col += 1

    Data["PTDF-matrix"] = PTDF
    return Data


# ---------------------------------------------------------------------------
# Pyomo model
# ---------------------------------------------------------------------------

def _run_model(Data, solver="gurobi", verbose=False):
    model = pyo.ConcreteModel()

    # --- Sets ---
    model.L = pyo.Set(ordered=True, initialize=Data["AC-lines"]["ACList"])
    model.N = pyo.Set(ordered=True, initialize=Data["Nodes"]["NodeList"])
    model.H = pyo.Set(ordered=True, initialize=Data["DC-lines"]["DCList"])

    # --- Parameters ---
    model.Demand    = pyo.Param(model.N, initialize=Data["Nodes"]["DEMAND"])
    model.P_min     = pyo.Param(model.N, initialize=Data["Nodes"]["GENMIN"])
    model.P_max     = pyo.Param(model.N, initialize=Data["Nodes"]["GENCAP"])
    model.Cost_gen  = pyo.Param(model.N, initialize=Data["Nodes"]["GENCOST"])
    model.Cost_shed = pyo.Param(initialize=Data["ShedCost"])

    model.P_AC_max = pyo.Param(model.L, initialize=Data["AC-lines"]["Cap From"])
    model.P_AC_min = pyo.Param(model.L, initialize=Data["AC-lines"]["Cap To"])
    model.AC_from  = pyo.Param(model.L, initialize=Data["AC-lines"]["From"])
    model.AC_to    = pyo.Param(model.L, initialize=Data["AC-lines"]["To"])

    model.DC_cap = pyo.Param(model.H, initialize=Data["DC-lines"]["Cap"])

    # --- Variables ---
    model.gen        = pyo.Var(model.N, within=pyo.Reals)
    model.shed       = pyo.Var(model.N, within=pyo.NonNegativeReals)
    model.flow_AC    = pyo.Var(model.L, within=pyo.Reals)
    model.flow_DC    = pyo.Var(model.H, within=pyo.Reals)
    model.injections = pyo.Var(model.N, within=pyo.Reals)

    # --- Objective ---
    def ObjRule(m):
        return (sum(m.gen[n]  * m.Cost_gen[n] for n in m.N) +
                sum(m.shed[n] * m.Cost_shed    for n in m.N))
    model.OBJ = pyo.Objective(rule=ObjRule, sense=pyo.minimize)

    # --- Generation bounds ---
    model.Min_gen_const = pyo.Constraint(model.N, rule=lambda m, n: m.gen[n] >= m.P_min[n])
    model.Max_gen_const = pyo.Constraint(model.N, rule=lambda m, n: m.gen[n] <= m.P_max[n])

    # --- AC line flow bounds ---
    model.From_flow_L = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] <=  m.P_AC_max[l])
    model.To_flow_L   = pyo.Constraint(model.L, rule=lambda m, l: m.flow_AC[l] >= -m.P_AC_min[l])

    # --- DC cable bounds ---
    model.FlowBalDC_max_const = pyo.Constraint(model.H, rule=lambda m, h: m.flow_DC[h] <=  m.DC_cap[h])
    model.FlowBalDC_min_const = pyo.Constraint(model.H, rule=lambda m, h: m.flow_DC[h] >= -m.DC_cap[h])

    # --- Balance constraints (FBMC vs ATC) ---
    if Data["DCFlow"]:
        # Injection definition: inj_n = gen_n - demand_n + shed_n - sum(DC_hn * flow_DC_h)
        def InjDef(m, n):
            return m.injections[n] == (m.gen[n] - m.Demand[n] + m.shed[n]
                   - sum(Data["DC-matrix"][h-1, n-1] * m.flow_DC[h] for h in m.H))
        model.InjDef_const = pyo.Constraint(model.N, rule=InjDef)

        # PTDF: flow_l = sum(PTDF_ln * inj_n)
        def FlowBal(m, l):
            return m.flow_AC[l] == sum(Data["PTDF-matrix"][l-1, n-1] * m.injections[n] for n in m.N)
        model.FlowBal_const = pyo.Constraint(model.L, rule=FlowBal)

        # System-wide injection balance
        model.SystemBalance_const = pyo.Constraint(
            rule=lambda m: sum(m.injections[n] for n in m.N) == 0)

    else:
        # ATC / transport: nodal power balance (Kirchhoff's current law via incidence matrix)
        def LoadBal(m, n):
            return (m.gen[n] + m.shed[n]
                    == m.Demand[n]
                    + sum(Data["X-matrix"][l-1, n-1]  * m.flow_AC[l] for l in m.L)
                    + sum(Data["DC-matrix"][h-1, n-1] * m.flow_DC[h] for h in m.H))
        model.LoadBal_const = pyo.Constraint(model.N, rule=LoadBal)

    # --- Solve ---
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    opt        = pyo.SolverFactory(solver)
    sol        = opt.solve(model, load_solutions=True, tee=verbose)

    if verbose:
        sol.write(num=1)

    # --- Extract results ---
    if Data["DCFlow"]:
        prices     = {n: model.dual[model.InjDef_const[n]]  for n in model.N}
        shadow_ac  = {l: model.dual[model.FlowBal_const[l]] for l in model.L}
        shadow_ub  = {}
        shadow_lb  = {}
    else:
        prices    = {n: model.dual[model.LoadBal_const[n]] for n in model.N}
        shadow_ac = {}
        shadow_ub = {l: model.dual[model.From_flow_L[l]]  for l in model.L}
        shadow_lb = {l: model.dual[model.To_flow_L[l]]    for l in model.L}

    results = {
        "objective":    model.OBJ(),
        "gen":          {n: model.gen[n].value      for n in model.N},
        "shed":         {n: model.shed[n].value      for n in model.N},
        "prices":       prices,
        "flow_ac":      {l: model.flow_AC[l].value   for l in model.L},
        "flow_dc":      {h: model.flow_DC[h].value   for h in model.H},
        "shadow_ac":    shadow_ac,
        "shadow_ac_ub": shadow_ub,
        "shadow_ac_lb": shadow_lb,
        "demand":       {n: model.Demand[n]          for n in model.N},
        "node_names":   Data["Nodes"]["NNAMES"],
        "dcflow":       Data["DCFlow"],
        "Data":         Data,
    }
    return results


# ---------------------------------------------------------------------------
# Pretty-print helpers (used by task scripts)
# ---------------------------------------------------------------------------

def print_generation_table(res, title="Generation & Prices"):
    """Print a node-level generation / price table."""
    names  = res["node_names"]
    gen    = res["gen"]
    shed   = res["shed"]
    prices = res["prices"]
    demand = res["demand"]

    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")
    print(f"{'Node':<6} {'Name':<6} {'Demand':>8} {'Gen':>8} {'Shed':>8} {'Price':>10}")
    print(f"{'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
    for n in sorted(gen.keys()):
        print(f"{n:<6} {names[n]:<6} {demand[n]:>8.1f} {gen[n]:>8.1f} "
              f"{shed[n]:>8.2f} {prices[n]:>10.2f}")
    print(f"{'':6} {'TOTAL':<6} {sum(demand.values()):>8.1f} {sum(gen.values()):>8.1f} "
          f"{sum(shed.values()):>8.2f}")
    print(f"\n  Objective (total cost): {res['objective']:,.2f} €")
    print(f"  Method: {'FBMC (DC flow)' if res['dcflow'] else 'ATC (transport)'}")


def print_congestion_table(res, title="AC Line Flows & Congestion Rent"):
    """Print AC line flows and congestion rent = flow * (price_to - price_from)."""
    Data    = res["Data"]
    flow_ac = res["flow_ac"]
    prices  = res["prices"]
    names   = res["node_names"]

    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
    print(f"{'Line':<5} {'From':>6} {'To':>6} {'Flow':>8} {'Cap+':>7} {'Cap-':>7} "
          f"{'π_to-π_fr':>10} {'CR':>10}")
    print(f"{'-'*5} {'-'*6} {'-'*6} {'-'*8} {'-'*7} {'-'*7} {'-'*10} {'-'*10}")

    total_cr = 0.0
    for l in sorted(flow_ac.keys()):
        fr   = Data["AC-lines"]["From"][l]
        to   = Data["AC-lines"]["To"][l]
        cap  = Data["AC-lines"]["Cap From"][l]
        cap2 = Data["AC-lines"]["Cap To"][l]
        fl   = flow_ac[l]
        dp   = prices[to] - prices[fr]
        cr   = fl * dp
        total_cr += cr
        print(f"{l:<5} {names[fr]:>6} {names[to]:>6} {fl:>8.1f} {cap:>7.0f} {cap2:>7.0f} "
              f"{dp:>10.2f} {cr:>10.2f}")

    print(f"\n  Total congestion rent: {total_cr:,.2f} €/h")


def compute_congestion_rent(res):
    """Return dict {line: CR} and total CR."""
    Data    = res["Data"]
    flow_ac = res["flow_ac"]
    prices  = res["prices"]
    cr      = {}
    for l, fl in flow_ac.items():
        fr      = Data["AC-lines"]["From"][l]
        to      = Data["AC-lines"]["To"][l]
        cr[l]   = fl * (prices[to] - prices[fr])
    return cr, sum(cr.values())
