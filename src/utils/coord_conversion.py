import numpy as np 
import pandas as pd

def galactic_to_cartesian(df, l_colname='l', b_colname='b', r_colname=None):
    l_rad = np.radians(df[l_colname])
    b_rad = np.radians(df[b_colname])

    r = 1
    if r_colname:
        r = df[r_colname]

    x = r * np.cos(b_rad) * np.cos(l_rad)
    y = r * np.cos(b_rad) * np.sin(l_rad)
    z = r * np.sin(b_rad)
    return x, y, z