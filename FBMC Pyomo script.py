import numpy as np
import sys
import time
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

def Main():
    Data = Read_Excel("Nordic_wet.xlsx")
    if any([Data["Reference node"] <= 0, Data["Reference node"] > Data["Nodes"]["NumNodes"]]):
        print("Invalid reference node, the number of nodes does not allow this node to be reference!")
        sys.exit()
    if all((Data["DCFlow"] != 1, Data["DCFlow"] != 0)):
        print("Invalid method chosen. Either choose 1 or 0")
        sys.exit()

    Data = Create_matrices(Data)
    Data = Calculate_PTDF(Data)  # Calculate PTDF matrix

    FBMC_model(Data)



    return()


def Read_Excel(name):
    """
    Reads input excel file and reads the data into dataframes.
    Separates between each sheet, and stores into one dictionary
    """

    data = {}  # Dictionary storing the input data

    Excel_sheets = ["Node Parameters", "AC Branch Parameters", "DC Link Parameters"]  # Name of each sheet
    Data_names = {"Node Parameters": "Nodes", "AC Branch Parameters": "AC-lines",
                  "DC Link Parameters": "DC-lines"}  # Names for data for each sheet
    Num_Names = {"Node Parameters": "NumNodes", "AC Branch Parameters": "NumAC",
                 "DC Link Parameters": "NumDC"}  # Names for numbering
    List_Names = {"Node Parameters": "NodeList", "AC Branch Parameters": "ACList",
                  "DC Link Parameters": "DCList"}  # Names for numbering

    for sheet in Excel_sheets:  # For each sheet
        df = pd.read_excel(name, sheet_name=sheet, skiprows=1)  # Read sheet, exclude title

        df = df.set_index(df.columns[0])  # Set first column as index
        num = len(df.loc[:])  # Find length of dataframe
        df = df.to_dict()

        df[Num_Names[sheet]] = num  # Store length of dataframe in dictionary
        df[List_Names[sheet]] = np.arange(1, num + 1)

        data[Data_names[sheet]] = df  # Store dataframe in dictionary

        # End for

    # Extract data from the declaration sheet

    df = pd.read_excel(name, sheet_name="Declarations", skiprows=1)  # Get from Declaration sheet
    df = df.set_index(df.columns[0])  # Make first column index
    df = df.to_dict()  # Convert to dictionary

    data["DCFlow"] = df["Value"][1]  # True: DC power flow, False: Transport network (ATC)
    data["Reference node"] = df["Value"][2]  # The reference node where Theta = 0
    data["ShedCost"] = df["Value"][4]  # Cost of shedding load

    return (data)  # Return datasheet


def Create_matrices(Data):
    """
    Setting up matrices for the problems:
        - B-matrix  -> Admittance matrix for the lines. Used in DCOPF/PTDF calculation
        - DC-matrix -> Bus incidence matrix for the DC cables. Used in both DCOPF/PTDF calculation and ATC
        - X-matrix  -> Bus incidence matrix for AC cables. Used in ATC
    """

    # Start creating admittance matrix X. Adding in [n-1] is due to avoiding the 0-th index. This is only for DCOPF/PTDF calculation, not used in the optimization model itself

    B_matrix = np.zeros((Data["Nodes"]["NumNodes"], Data["Nodes"]["NumNodes"]))  # Create empty matrix

    for n in range(1, Data["Nodes"]["NumNodes"] + 1):  # For every starting node
        for o in range(1, Data["Nodes"]["NumNodes"] + 1):  # For every ending node
            for l in range(1, Data["AC-lines"]["NumAC"] + 1):  # For every line
                if n == Data["AC-lines"]["From"][l]:  # If starting node corresponds to start in line l
                    if o == Data["AC-lines"]["To"][l]:  # If ending node corresponds to end in line l

                        B_matrix[n - 1][o - 1] = B_matrix[n - 1][o - 1] - Data["AC-lines"]["Admittance"][
                            l]  # Admittance added in [n-1,o-1]

                        B_matrix[o - 1][n - 1] = B_matrix[o - 1][n - 1] - Data["AC-lines"]["Admittance"][
                            l]  # Admittance added in [o-1,n-1]

                        B_matrix[n - 1][n - 1] = B_matrix[n - 1][n - 1] + Data["AC-lines"]["Admittance"][
                            l]  # Admittance added in [n-1,n-1]

                        B_matrix[o - 1][o - 1] = B_matrix[o - 1][o - 1] + Data["AC-lines"]["Admittance"][
                            l]  # Admittance added in [n-1,n-1]

    Data["B-matrix"] = B_matrix  # Store the matrix in the dictionary

    # Start creating the DC-matrix
    DC_matrix = np.zeros((Data["DC-lines"]["NumDC"], Data["Nodes"]["NumNodes"]))  # Dimension CablesxNodes [h,n]

    for h in range(1, Data["DC-lines"]["NumDC"] + 1):  # For each cable

        node_pos = Data["DC-lines"]["From"][h]  # Find the starting node of the cable
        DC_matrix[h - 1][
            node_pos - 1] = 1  # Store the cable in the matrix for -1 position. Store value as 1 (meaning positive direction of flow)

        node_pos = Data["DC-lines"]["To"][h]  # Find the ending node of the cable
        DC_matrix[h - 1][
            node_pos - 1] = -1  # Store the cable in the matrix for -1 position. Store value as -1 (meaning negative direction of flow)

    Data["DC-matrix"] = DC_matrix  # Store the matrix in the dictionary

    # Start creating the X-matrix

    X_matrix = np.zeros((Data["AC-lines"]["NumAC"], Data["Nodes"]["NumNodes"]))  # Dimension LinesxNodes [l,n]

    for l in range(1, Data["AC-lines"]["NumAC"] + 1):  # For each line

        node_pos = Data["AC-lines"]["From"][l]  # Find the starting node
        X_matrix[l - 1][node_pos - 1] = 1  # Store the line starting position as a value 1

        node_pos = Data["AC-lines"]["To"][l]  # Find the ending node
        X_matrix[l - 1][node_pos - 1] = -1  # Store the line ending position as a value -1

    Data["X-matrix"] = X_matrix  # Store the matrix in the dictionary

    return (Data)


def Calculate_PTDF(Data):
    """
    Calculate the PTDF matrix using the B matrix and incidence matrix.
    """
    # Get the B matrix and incidence matrix
    B_matrix = Data["B-matrix"]
    X_matrix = Data["X-matrix"]

    # Number of nodes and lines
    num_nodes = Data["Nodes"]["NumNodes"]
    num_lines = Data["AC-lines"]["NumAC"]

    # Reference node
    ref_node = Data["Reference node"]

    # Remove the reference node from B matrix
    B_reduced = np.delete(np.delete(B_matrix, ref_node - 1, axis=0), ref_node - 1, axis=1)

    # Invert the reduced B matrix
    B_reduced_inv = np.linalg.inv(B_reduced)


    # Calculate PTDF matrix by multiplying the 𝑑𝑖𝑎𝑔𝑜𝑛𝑎𝑙 𝑚𝑎𝑡𝑟𝑖𝑥 𝑜𝑓 1/𝑙𝑖𝑛𝑒 𝑟𝑒𝑎𝑐𝑡𝑎𝑛𝑐 * incidence matrix A * inverse of B-reduced
    A = X_matrix.copy()  # lines x nodes incidence matrix (+1 from, -1 to)
    A_reduced = np.delete(A, ref_node - 1, axis=1)  # remove reference node column -> (lines x (N-1))

    # Build susceptance vector in line order 1..num_lines
    b_vec = np.array([Data["AC-lines"]["Admittance"][l] for l in range(1, num_lines + 1)])  # shape (lines,)

    # Form diagonal matrix of line susceptances
    B_line = np.diag(b_vec)  # (lines x lines)

    # Compute reduced PTDF (lines x (N-1))
    OmegaA = B_line.dot(A_reduced)
    PTDF_reduced = OmegaA.dot(B_reduced_inv)

    PTDF = np.zeros((num_lines, num_nodes))
    col = 0
    for n in range(num_nodes):
        if n == ref_node - 1:
            PTDF[:, n] = 0.0
        else:
            PTDF[:, n] = PTDF_reduced[:, col]
            col += 1

    Data["PTDF-matrix"] = PTDF

    return Data

def FBMC_model(Data):
    model = pyo.ConcreteModel()

    # Sets
    model.L = pyo.Set(ordered=True, initialize=Data["AC-lines"]["ACList"])
    model.N = pyo.Set(ordered=True, initialize=Data["Nodes"]["NodeList"])
    model.H = pyo.Set(ordered=True, initialize=Data["DC-lines"]["DCList"])

    # Parameters
    model.Demand = pyo.Param(model.N, initialize=Data["Nodes"]["DEMAND"])
    model.P_min = pyo.Param(model.N, initialize=Data["Nodes"]["GENMIN"])
    model.P_max = pyo.Param(model.N, initialize=Data["Nodes"]["GENCAP"])
    model.Cost_gen = pyo.Param(model.N, initialize=Data["Nodes"]["GENCOST"])
    model.Cost_shed = pyo.Param(initialize=Data["ShedCost"])

    # AC-lines
    model.P_AC_max = pyo.Param(model.L, initialize=Data["AC-lines"]["Cap From"])
    model.P_AC_min = pyo.Param(model.L, initialize=Data["AC-lines"]["Cap To"])
    model.AC_from = pyo.Param(model.L, initialize=Data["AC-lines"]["From"])
    model.AC_to = pyo.Param(model.L, initialize=Data["AC-lines"]["To"])

    # DC-lines
    model.DC_cap = pyo.Param(model.H, initialize=Data["DC-lines"]["Cap"])

    # Variables
    model.gen = pyo.Var(model.N)
    model.shed = pyo.Var(model.N, within=pyo.NonNegativeReals)
    model.flow_AC = pyo.Var(model.L, within=pyo.Reals)
    model.flow_DC = pyo.Var(model.H, within=pyo.Reals)
    model.injections = pyo.Var(model.N)

    # Objective function
    def ObjRule(model):
        return (sum(model.gen[n] * model.Cost_gen[n] for n in model.N) + sum(model.shed[n] * model.Cost_shed for n in model.N))
    model.OBJ = pyo.Objective(rule=ObjRule, sense=pyo.minimize)

    # Constraints
    def Min_gen(model, n):
        return model.gen[n] >= model.P_min[n]
    model.Min_gen_const = pyo.Constraint(model.N, rule=Min_gen)

    def Max_gen(model, n):
        return model.gen[n] <= model.P_max[n]
    model.Max_gen_const = pyo.Constraint(model.N, rule=Max_gen)

    def From_flow(model, l):
        return model.flow_AC[l] <= model.P_AC_max[l]
    model.From_flow_L = pyo.Constraint(model.L, rule=From_flow)

    def To_flow(model, l):
        return model.flow_AC[l] >= -model.P_AC_min[l]
    model.To_flow_L = pyo.Constraint(model.L, rule=To_flow)

    def FlowBalDC_max(model, h):
        return model.flow_DC[h] <= model.DC_cap[h]
    model.FlowBalDC_max_const = pyo.Constraint(model.H, rule=FlowBalDC_max)

    def FlowBalDC_min(model, h):
        return model.flow_DC[h] >= -model.DC_cap[h]
    model.FlowBalDC_min_const = pyo.Constraint(model.H, rule=FlowBalDC_min)

    if Data["DCFlow"] == True:
        # define nodal injection explicitly (clean, avoids nested sums inside PTDF constraint)
        def InjDef(model, n):
            return model.injections[n] == model.gen[n] - model.Demand[n] + model.shed[n] - sum(Data["DC-matrix"][h - 1, n - 1] * model.flow_DC[h] for h in model.H)
        model.InjDef_const = pyo.Constraint(model.N, rule=InjDef)

        # PTDF maps nodal injections (including DC injections) -> AC line flows
        def FlowBal(model, l):
            return model.flow_AC[l] == sum(Data["PTDF-matrix"][l - 1, n - 1] * model.injections[n] for n in model.N)

        model.FlowBal_const = pyo.Constraint(model.L, rule=FlowBal)

        def SystemBalance(model):
            return sum(model.injections[n] for n in model.N) == 0
        model.SystemBalance_const = pyo.Constraint(rule=SystemBalance)

    else:
        def LoadBal(model, n):
            return model.gen[n] + model.shed[n] == model.Demand[n] + sum(Data["X-matrix"][l - 1, n - 1] * model.flow_AC[l] for l in model.L) + sum(Data["DC-matrix"][h - 1, n - 1] * model.flow_DC[h] for h in model.H)
        model.LoadBal_const = pyo.Constraint(model.N, rule=LoadBal)

    # Solve the problem
    #opt = pyo.SolverFactory("glpk")
    opt = pyo.SolverFactory("gurobi")
    #results = opt.solve(model, tee=True, suffixes=['dual'])
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    results = opt.solve(model, load_solutions=True)
    results.write(num=1)
    Store_model_data(model, Data)

    print("\n\n")
    print("The optimization model has been solved, the results are now being stored in an excel file")
    print("Objective value: " + str(round(model.OBJ(), 4)))
    print("FLOW AC: " + str({l: round(model.flow_AC[l].value, 4) for l in model.L}))
    print("FLOW DC: " + str({h: round(model.flow_DC[h].value, 4) for h in model.H}))
    print("Production: " + str({n: round(model.gen[n].value, 4) for n in model.N}))
    print("Shedding: " + str({n: round(model.shed[n].value, 4) for n in model.N}))
    print("Demand: " + str({n: round(model.Demand[n], 4) for n in model.N}))
    if Data["DCFlow"] == True:
        print("Prices: " + str({n: round(model.dual[model.InjDef_const[n]], 4) for n in model.N}))
    else:
        print("Prices: " + str({n: round(model.dual[model.LoadBal_const[n]], 4) for n in model.N}))
    return()


def Store_model_data(model, Data):
    """
    Stores the results from the optimization model run into an excel file (FBMC model)
    """

    # Create empty dictionaries that will be filled
    NodeData = {}
    ACData = {}
    DCData = {}
    MiscData = {}

    # Node data dictionaries
    Gen = {}
    Shed = {}
    Demand = {}
    CostGen = {}
    CostShed = {}
    Injections = {}
    Price = {}

    # For every node, store the data in the respective dictionary
    for node in model.N:
        Gen[node] = round(model.gen[node].value, 4)
        Shed[node] = round(model.shed[node].value, 4)
        Demand[node] = round(model.Demand[node], 4)
        CostGen[node] = round(model.gen[node].value * model.Cost_gen[node], 4)
        CostShed[node] = round(model.shed[node].value * model.Cost_shed, 4)

        if Data["DCFlow"] == True:
            Price[node] = round(model.dual[model.InjDef_const[node]], 4)
            Injections[node] = round(model.injections[node].value, 4)
        else:
            Price[node] = round(model.dual[model.LoadBal_const[node]], 4)

    # Store Node Data
    NodeData["Gen"] = Gen
    NodeData["Shed"] = Shed
    NodeData["Demand"] = Demand
    NodeData["MargCost"] = Data["Nodes"]["GENCOST"]
    NodeData["CostGen"] = CostGen
    NodeData["CostShed"] = CostShed
    NodeData["Node Name"] = Data["Nodes"]["NNAMES"]
    NodeData["Price (dual)"] = Price
    if Data["DCFlow"] == True:
        NodeData["Injections"] = Injections
    # AC-line data
    ACFlow = {}
    DualFlow = {}
    DualFrom    = {}
    DualTo      = {}

    for line in model.L:
        ACFlow[line] = round(model.flow_AC[line].value, 4)
        if Data["DCFlow"] == True:
            DualFlow[line] = round(model.dual[model.FlowBal_const[line]], 4)
        else:
            DualFrom[line]      = round(model.dual[model.From_flow_L[line]],1)
            DualTo[line]        = round(model.dual[model.To_flow_L[line]],1)


    ACData["AC Flow"] = ACFlow
    ACData["Max power from"] = Data["AC-lines"]["Cap From"]
    ACData["Max power to"] = Data["AC-lines"]["Cap To"]
    ACData["From Node"] = Data["AC-lines"]["From"]
    ACData["To Node"] = Data["AC-lines"]["To"]
    if Data["DCFlow"] == True:
        ACData["Admittance"] = Data["AC-lines"]["Admittance"]
        ACData["Dual Value (shadow price)"] = DualFlow
    else:
        ACData["Dual From"] = DualFrom
        ACData["Dual To"] = DualTo

    # DC-line data
    DCFlow = {}

    for cable in model.H:
        DCFlow[cable] = round(model.flow_DC[cable].value, 4)

    DCData["DC Flow"] = DCFlow
    DCData["Capacity"] = Data["DC-lines"]["Cap"]
    DCData["From Node"] = Data["DC-lines"]["From"]
    DCData["To Node"] = Data["DC-lines"]["To"]

    # Misc
    Objective = round(model.OBJ(), 4)

    MiscData["Objective"] = {1: Objective}
    if Data["DCFlow"] == False:
        MiscData["Method"] = {1: "ATC (Transport network)"}
    else:
        MiscData["Method"] = {1: "FBMC (PTDF-based DCOPF)"}




    # Convert the dictionaries to DataFrames
    NodeData = pd.DataFrame(data=NodeData)
    ACData = pd.DataFrame(data=ACData)
    DCData = pd.DataFrame(data=DCData)
    MiscData = pd.DataFrame(data=MiscData)

    if Data["DCFlow"] == True:
        output_file = "FBMC_results.xlsx"
    else:
        output_file = "ATC_results.xlsx"

    # Store each result in an excel file, given a separate sheet
    with pd.ExcelWriter(output_file) as writer:
        NodeData.to_excel(writer, sheet_name="Node")
        ACData.to_excel(writer, sheet_name="AC")
        DCData.to_excel(writer, sheet_name="DC")
        MiscData.to_excel(writer, sheet_name="Misc")

    print("\n\n")
    print("The results are now stored in the excel file: " + output_file)
    print("This program will now end")

    return ()


Main()
