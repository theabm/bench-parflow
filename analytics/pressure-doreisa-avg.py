import asyncio
import doreisa.head_node as doreisa
import dask.array as da
import numpy as np
import os
import time

doreisa.init()

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
    
# window of size 2
asyncio.run(doreisa.start(simulation_callback, [
    doreisa.DaskArrayInfo("pressures", window_size=1),
]))
