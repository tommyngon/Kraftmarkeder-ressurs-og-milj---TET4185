# -*- coding: utf-8 -*-
"""
Created on Thu Jan 31 17:08:59 2019

@author: kasperet
"""

import numpy as np
import sys
import time
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import matplotlib.pyplot as plt


name = "Area_Input.xlsx"

df = pd.read_excel( name, sheet_name = "Connection", skiprows = 1)

df = df.set_index(df.columns[0])

df = df.to_dict()

df["Actual Transfer"] = {1:250}

df_new = pd.DataFrame(data=df)

df_new.to_excel(pd.ExcelWriter("Output_excel.xlsx"), sheet_name = "Cool title")
