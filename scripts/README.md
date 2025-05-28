# Scripts

## Build

To build the benchmark, first set the environment for building. Follow the directions in `env/` for either guix or spack.

Once the environment is correctly set, simply run:
```bash
bash root_of_repo/scripts/build/build-all.sh
```
This script builds PDI, fetches Deisa and Doreisa, and builds parflow. 

To build invididual parts and speed up the process, run:
```bash
bash root_of_repo/scripts/build/build-<component-of-interest>.sh
```

## Run

Before running, activate the environment by following the instructions in `env/`. There are a few possibilities to run the analytics and simulation:

1. Run parflow standalone - `bash root_of_project/scripts/run/start_multinode_parflow.sh` : Run parflow on any number of nodes. For multinode setup, make sure that the number of nodes is a perfect square.
2. Run parflow with analytics (DEISA) - `bash root_of_project/scripts/run/start_multinode_deisa_insitu.sh <case> [<ranksXdim> <ranksYdim>]` : Run with any number of nodes. For multnode setup, make sure that the number of nodes is a perfect square **PLUS ONE**. The `<case>` argument is an interger: 0 or 1. 0 runs the average case, 1 runs the derivative case. Optionally, you can pass the number of processes in each dimension (X and Y) PER NODE, i.e. running `bash scripts/start_multinode_deisa_insitu.sh 0 5 5` will run the average case with 25 mpi procs per node. 
3. Run parflow with analytics (DOREISA) - `bash root_of_project/scripts/run/start_multinode_doreisa.sh <case> [<ranksXdim> <ranksYdim>]` : Same description as above applies.


## Bench




