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

def simulation_callback(pressures: list[da.Array], timestep: int):
    start = time.perf_counter()

    avg_p = pressures[0].mean()

    end = time.perf_counter()
    timings_graph.append(end-start)


    start = time.perf_counter()

    avg_p = avg_p.compute()

    end = time.perf_counter()
    timings_compute.append(end-start)

    result.append(avg_p)

    if timestep == 9:
        print(f"-TIMINGS-\nTIMINGS GRAPH:\n{timings_graph}\nTIMINGS_COMPUTE:\n{timings_compute}", flush = True)

    #print(f"Simulation step: {timestep}\tAvg. Pressure: {avg_p}", flush=True)
    
# window of size 1
# if you want to do the preprocessing, you need to pass it as an argument
# to the daskarrayinfo 
# doreisa.DaskArrayInfo("pressures", window_size=1, preprocess_pressures)
# you should add a DaskArrayInfo for every array you will analyze

run_simulation(
    simulation_callback,
    [ArrayDefinition("pressures", window_size=1)],
    max_iterations=10,
)
