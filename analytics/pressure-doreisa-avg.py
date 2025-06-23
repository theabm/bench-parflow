import asyncio
import numpy as np
import os
import time

import dask.array as da
from doreisa.head_node import init
from doreisa.window_api import ArrayDefinition, run_simulation

init()

def preprocess_pressures(pressures: np.ndarray) -> np.ndarray:
    """
    Remove the ghost cells from the array.
    """
    # return pressures[1:-1, 1:-1]
    return pressures

result = []
timings_graph = []
timings_compute = []

def simulation_callback(
    pressures: list[da.Array], 
    # saturations: list[da.Array], 
    timestep: int
    ):

    start_g = time.time()

    avg_p = pressures[0].mean()
    # avg_s = saturations[0].mean()

    end_g = time.time()

    time_info = (start_g, end_g, end_g - start_g)
    timings_graph.append(time_info)

    start_c = time.time()

    avg_p = avg_p.compute()
    # avg_s = avg_s.compute()

    end_c = time.time()

    time_info = (start_c, end_c, end_c - start_c)
    timings_compute.append(time_info)

    print(f"[DOREISA, {timestep}] START : {start_g} END : {end_c} DIFF : {end_c - start_g}")

    if timestep == 9:
        print(f"[DOREISA, LAST STEP]\nTIMINGS GRAPH: {timings_graph}\nTIMINGS COMPUTE: {timings_compute}")

# window of size 1
# if you want to do the preprocessing, you need to pass it as an argument
# to the daskarrayinfo 
# doreisa.DaskArrayInfo("pressures", window_size=1, preprocess_pressures)
# you should add a DaskArrayInfo for every array you will analyze
print("Before Run Simulation")
run_simulation(
    simulation_callback,
    [
        ArrayDefinition("pressures", window_size=1),
        # ArrayDefinition("saturations", window_size=1),
    ],
    max_iterations=10,
)
