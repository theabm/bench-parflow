###################################################################################################
# Copyright (c) 2020-2022 Centre national de la recherche scientifique (CNRS)
# Copyright (c) 2020-2022 Commissariat a l'énergie atomique et aux énergies alternatives (CEA)
# Copyright (c) 2020-2022 Institut national de recherche en informatique et en automatique (Inria)
# Copyright (c) 2020-2022 Université Paris-Saclay
# Copyright (c) 2020-2022 Université de Versailles Saint-Quentin-en-Yvelines
#
# SPDX-License-Identifier: MIT
#
###################################################################################################

from deisa import Deisa
from dask.distributed import performance_report, wait
import os
import yaml
import dask
import sys

# Initialize Deisa
if len(sys.argv) < 3:
    raise Exception("Number of dask workers not set. Usage: python3 bench_deisa.py <n_dask_workers> <scheduler_file_name>")
else:
    nb_dask_workers = int(sys.argv[1])
    scheduler_file_name=str(sys.argv[2])
    print(f"parameters: dask workers - {nb_dask_workers}, scheduler_file - {scheduler_file_name}", flush=True)

analytics = Deisa(scheduler_file_name=scheduler_file_name,
              nb_expected_dask_workers=nb_dask_workers,
              use_ucx=False)

client = analytics.client

with performance_report(filename="dask-report.html"), dask.config.set( # type: ignore
    array_optimize=None
):
    p = analytics["global_pressure", :, :, :, :]
    analytics.ready()

    print("shape: ",  p.shape)

    # Construct a lazy task graph
    # mean over time
    psum = p.sum(axis = (1,2,3))

    # Submit the task graph to the scheduler
    # scheduler gets the graph and doesnt do anything yet.
    totcells = 1
    for cells in p.shape[1:]:
        totcells *= cells
    print(f"{totcells=}")
    
    psum = psum.compute()
    print(f"Sum of pressure per timestep: {psum}")
    psum = psum/totcells

    print(f"Average of pressure per timestep: {psum}")

print("Done", flush=True)
analytics.wait_for_last_bridge_and_shutdown()

