import asyncio
import doreisa.head_node as doreisa
import dask.array as da
import numpy as np
import os

doreisa.init()

def preprocess_pressures(pressures: np.ndarray) -> np.ndarray:
    """
    Remove the ghost cells from the array.
    """
    # return pressures[1:-1, 1:-1]
    return pressures

result = []

def simulation_callback(pressures: list[da.Array], timestep: int):
    avg_p = pressures[0].mean().compute()
    result.append(avg_p)
    #print(f"Simulation step: {timestep}\tAvg. Pressure: {avg_p}", flush=True)
    
# window of size 2
asyncio.run(doreisa.start(simulation_callback, [
    doreisa.DaskArrayInfo("pressures", window_size=1),
]))

print(f"Result : {result}")
