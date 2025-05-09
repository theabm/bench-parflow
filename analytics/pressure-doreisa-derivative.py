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

    #Derivative of a specific time step
    if timestep == 1:
        # derivative (central difference) 
        # derivative_p = ((pressures[2] - pressures[0])/(2 * 2)).compute()
        derivative_p = ((pressures[2] - pressures[0])/(2 * 2)).mean().compute()
        result.append(derivative_p)
    
asyncio.run(doreisa.start(simulation_callback, [
    doreisa.DaskArrayInfo("pressures", window_size=3),
]))

print(f"Result : {result}")
