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

def simulation_callback(pressures: list[da.Array], timestep: int):
    if timestep < 2:

        # Even though the window is set to 3, we still can operate on the first two 
        # timesteps, provided that we dont need 3 steps. For example:
        # this will print for timestep 0 and 1
        avg_p = pressures[timestep].mean().compute()
        print(f"BEFORE FULL WINDOW: Simulation step: {timestep}\tAvg. Pressure: {avg_p}", flush=True)
    else:   
        # when I have at least 3 timesteps, I recenter the calculations for the 
        # window (so it will be timestep - 1) so that my time derivatives, integral, etc. take the
        # previous and next timestep into account.

        # take the middle timestep of the window
        avg_p = pressures[1].mean().compute()
        print(f"AFTER FULL WINDOW: Simulation step: {timestep-1}\tAvg. Pressure: {avg_p}", flush=True)

        # Advantage over Deisa: we can do conditional calculations!

        # if the average pressure is between -5.9 and -6.0, we calculate the std deviation, integral, and derivative
        if avg_p < -5.9 and avg_p > -6.0: 
            print("Critical point reached! New calculating std deviation, integral, and derivative")
            std_p = pressures[1].std().compute()

            # integral (Simpsons rule) - window = 3 means (b-a = 2) 
            # this prints the entire array
            # integral_p = ((pressures[2] + pressures[0] + 4 * pressures[1])/3).compute()
            integral_p = ((pressures[2] + pressures[0] + 4 * pressures[1])/3).mean().compute()

            # derivative (central difference) 
            # this prints the entire array
            # derivative_p = ((pressures[2] - pressures[0])/(2 * 2)).compute()
            derivative_p = ((pressures[2] - pressures[0])/(2 * 2)).mean().compute()
            print(f"AFTER FULL WINDOW + ADDITIONAL CALCULATIONS: Timestep: {timestep -1}\t Avg. Pressure: {avg_p}\t Std. Dev. Pressure: {std_p}\t Integral: {integral_p}\t Derivative: {derivative_p}", flush=True)
    
# window of size 2
asyncio.run(doreisa.start(simulation_callback, [
    doreisa.DaskArrayInfo("pressures", window_size=3),
]))
