# TET4185 Power Markets — Group Project Code Repository

**Group:** Tommy Nguyen · Ada-Lill Aarhus · Malin Nupen  
**Course:** TET4185 Power Markets, NTNU  

This repository contains all Python code that generates the results, tables, and figures in the project report.

---

## Structure

```
code/
├── FBMC_Pyomo_original.py      ← Original course script (unchanged reference)
├── data/
│   ├── Nordic_wet.xlsx         ← Nordic 12-node wet-year input data
│   ├── Nordic_dry.xlsx         ← Nordic 12-node dry-year input data
│   └── Problem2_data.xlsx      ← 3-node system for Problem 2
├── problem2/
│   └── dcopf_3node.py          ← Tasks 2-2 through 2-5
├── problem3/
│   ├── nordic_base.py          ← Shared solver module (imported by all scripts)
│   ├── task3_2_wet_year.py     ← Tables A.1, A.2
│   ├── task3_3_dry_year.py     ← Tables A.3, A.4, A.5
│   ├── task3_4_nuclear_phaseout.py  ← Tables A.6, A.7
│   └── task3_5_carbon_price.py     ← Tables A.8, A.9, A.10
└── problem4/
    ├── task4_1_wind_integration.py  ← Table A.11
    ├── task4_2_peak_demand.py       ← Table A.12
    └── task4_3_supply_scarcity.py   ← Table A.13
```

---

## Setup

### Requirements

- Python 3.9+
- Gurobi (academic license required — free for students: https://www.gurobi.com/academia/)

```bash
pip install -r requirements.txt
```

### Gurobi license

Register at gurobi.com with your university email. After installing `gurobipy`, activate with:

```bash
grbgetkey <your-license-key>
```

---

## Running the scripts

All scripts should be run from the `code/` directory:

```bash
cd code/
```

### Problem 2 — 3-Node DCOPF

```bash
python problem2/dcopf_3node.py          # Run all tasks
python problem2/dcopf_3node.py 2-2      # Run only Task 2-2
python problem2/dcopf_3node.py 2-5      # Run only Task 2-5
```

### Problem 3 — Nordic 12-Node System

```bash
python problem3/task3_2_wet_year.py         # Tables A.1, A.2
python problem3/task3_3_dry_year.py         # Tables A.3, A.4, A.5
python problem3/task3_4_nuclear_phaseout.py # Tables A.6, A.7
python problem3/task3_5_carbon_price.py     # Tables A.8, A.9, A.10
```

### Problem 4 — Wind & Demand Scenarios

```bash
python problem4/task4_1_wind_integration.py # Table A.11
python problem4/task4_2_peak_demand.py      # Table A.12
python problem4/task4_3_supply_scarcity.py  # Table A.13
```

---

## Model overview

### FBMC (Flow-Based Market Coupling)

Uses the PTDF (Power Transfer Distribution Factor) matrix to enforce Kirchhoff's
voltage law on AC lines. The nodal price equals the dual of the injection-definition
constraint `InjDef_const[n]`.

The PTDF matrix is computed as:

```
H = B_line · A_reduced · B_reduced⁻¹
```

where `B_line` is the diagonal susceptance matrix, `A_reduced` is the
reduced incidence matrix (reference node column removed), and `B_reduced`
is the reduced nodal susceptance matrix.

### ATC (Available Transfer Capacity)

Transport-network model. AC line flows are free variables bounded only by thermal
capacities. The nodal price equals the dual of the per-node balance constraint
`LoadBal_const[n]`.

### Nordic 12-Node System

| Node | Zone | Country |
|------|------|---------|
| 1    | NO4  | Norway  |
| 2    | NO3  | Norway  |
| 3    | NO5  | Norway  |
| 4    | NO2  | Norway  |
| 5    | NO1  | Norway  |
| 6*   | SE1  | Sweden  |
| 7    | SE2  | Sweden  |
| 8    | SE3  | Sweden  |
| 9    | SE4  | Sweden  |
| 10   | FI   | Finland |
| 11   | DK1  | Denmark |
| 12   | DK2  | Denmark |

\* SE1 is the reference node (θ = 0).

---

## Key parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Load shedding cost | 3 200 €/MWh | Excel Declarations |
| SE3 nuclear capacity (base) | 12 400 MW | Nordic_wet.xlsx |
| SE3 nuclear capacity (phase-out) | 4 000 MW | Task 3-4 |
| Total wind installed | 22 900 MW | Task 4-1 |
| Peak demand scale | ×1.2 | Task 4-2/4-3 |

---

## Congestion rent

Congestion rent on line `l` is calculated as:

```
CR_l = flow_l × (λ_to − λ_from)
```

where `λ` is the nodal price (dual variable of the balance constraint).
