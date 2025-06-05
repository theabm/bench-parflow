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
import numpy as np

# Initialize Deisa
if len(sys.argv) < 5:
    raise Exception("Number of dask workers not set. Usage: python3 bench_deisa.py <n_dask_workers> <scheduler_file_name> <nb_mpi_workers>")
else:
    nb_dask_workers = int(sys.argv[1])
    scheduler_file_name=str(sys.argv[2])
    mpi_size = int(sys.argv[3])
    exp_dir = str(sys.argv[4])

mapping = {}
map_file = exp_dir + "/hostfile.txt"
with open(map_file, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
            hostname = line.strip()
            if line:
                mapping[i] = hostname + ":2000"

#print(f"Analytics got mapping: {mapping}\n")

def custom_mapping(size, workers_list):
  #print("########### DEISA Custom mapping function called! ###########\n")
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

    ###### AVERGARE BY TIMESTEP ######

    start = time.perf_counter()
    sum_p = p.mean(axis = (1,2,3))
    end = time.perf_counter()
    
    #Submit tasks graphs to the scheduler

    start2 = time.perf_counter()
    sum_p= sum_p.compute()
    end2 = time.perf_counter()

    print(f"""MEAN : {sum_p}, 
            ANALYTICS TIME : {end2 - start}, 
            time graph mean: {end - start}, 
            time compute: {end2 - start2}""", flush = True)

analytics.wait_for_last_bridge_and_shutdown()

