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

import deisa
from deisa import Deisa
from dask.distributed import performance_report, wait
import os
import yaml
import dask
import sys
import time

# Initialize Deisa
if len(sys.argv) < 5:
    raise Exception("Number of dask workers not set. Usage: python3 bench_deisa.py <n_dask_workers> <scheduler_file_name> <nb_mpi_workers>")
else:
    nb_dask_workers = int(sys.argv[1])
    scheduler_file_name=str(sys.argv[2])
    mpi_size = int(sys.argv[3])
    exp_dir = str(sys.argv[4])

mapping = {}
map_file = exp_dir + "/mapping.txt"
while True:
    if not os.path.exists(map_file):
        time.sleep(1)
        continue    
    else:
        with open(map_file, "r") as f:
            lines = f.readlines()
            if len(lines) >= mpi_size:
                for line in lines:
                    line = line.strip()
                    if line:
                        m_rank, m_hostname = line.split()
                        mapping[int(m_rank)] = m_hostname
                break
            else:
                time.sleep(1)

def custom_mapping(size, workers_list):
  print("########### DEISA Custom mapping function called! ###########\n")
  return mapping

deisa.set_mapping_implementation(custom_mapping)

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

