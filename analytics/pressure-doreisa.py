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

# print per time step
# keep all the averages
# save it to a file at the end
# if condition
def simulation_callback(pressures: list[da.Array], timestep: int):
    p = pressures[0].mean().compute()
    print(f"Simulation step: {timestep}\tAvg. Pressure: {p}", flush=True)
    

asyncio.run(doreisa.start(simulation_callback, [
    doreisa.DaskArrayInfo("pressures", window_size=1),
]))
