# Parflow In Situ Analytics

This repository aggreggates all the tools needed for running and benchmarking in-situ analytics 
with parflow-pdi.

## Structure

Below is the overall structure of the project. Each directory has more details. We go in more detail 
at the end.

### env/

The env directory contains all the necessary information and tools to setup the environment needed 
to run the benchmark. Currently, the most supported way of running is through spack, so we only list 
that. However, you will also find a `guix/` folder, which has the Guix recipe if you prefer. Beware 
that some dependencies were broken in Guix when we tried to use it, so we had to mix Guix with Python 
venvs, which added considerably to the complexity.

- `spack/`: contains all the `spack.yaml` which has the specification needed for the environment. 
Note that some slight adaptations will be needed for any new cluster. More is explained below and in 
the `env/` directory.

### scripts/

The scripts directory is the entry point for building, running, and benchmarking. It is usually 
structured in a folder, aptly named, and subfolders for each platform (for now: G5K and Leonardo). 
If you are using a slurm based system, the Leonardo directory is a good place to start.

- `build/`: contains all the scripts needed to build pdi, build parflow, and get the python deps.
- `run/`: contains all the scripts needed to run the simulation. Should be used mainly for interactive exploration.
- `bench/`: contains the scripts needed to submit a batch job using slurm or OAR.
- `utils/`: contains useful python scripts to poll memory usage, print clocktime info, and 
analyze and plot the results.
- `results/`: results of the benchmark run on leonardo.

### analytics/

Contains all python scripts to do in-situ analytics with Doreisa (Dask-on-ray enabled in situ 
analytics) and Deisa (Dask enabled in-situ analytics). It includes: a timestep average, a finite 
difference derivative, and a toy example which contains conditional analytics, triggered 
upon a specific event. 

## Getting Started

To get started:

1. Create a directory (`parflow/`) and enter it. This will contain everything related to this 
project.
2. Clone this repository: 
```
git clone https://github.com/theabm/bench-parflow
```
3. Clone the spack repository (set to specific commit) and activate spack: 
```
git clone https://github.com/spack/spack
cd spack
git checkout 84276915b9df365bb81b6186087ef1b66eedcc29
. share/spack/setup-env.sh
```

Note that this last command will always have to be executed whenever you open a new remote session.

4. Navigate to `env/spack/` and clone the `spack.numpex` repository, which is needed to get updated 
recipes for Ray: 
```
git clone https://github.com/viperML/spack.numpex
cd spack.numpex
git switch ray-update-1.0
```

5. Edit `spack.yaml` to contain the correct path to `spack.numpex`. 
6. Edit the spack recipes for `py-distributed` and `py-dask-expr` so that they can 
correctly build (this should be fixed in the future). Running the commands below will 
open the spack recipe in your favorite editor:
```
spack edit py-distributed
spack edit py-dask-expr
```

Change `py-versioneer@0.28+toml` to `py-versioneer@0.28:+toml`. Save an exit the changes.

7. Try to build the spack environment: 
```
spack env activate .
spack concretize -f
spack install
```

This might take a few hours. Once this is done (hopefully with no errors), you should have everything 
setup and ready to build and run the benchmark.

In the future, whenever you open a new session, you will have to activate spack and activate 
the environment 

```
. ~/parflow/spack/share/spack/setup-env.sh
spack env activate ~/parflow/bench-parflow/env/spack/
```

## Build

There are three components of the project: pdi, parflow, and python libraries.

First, activate the spack environment, then simply run:
```
bash scripts/build/build-all.sh
```

This will fetch all the dependencies and install them.

## Run

To run an analytic example - for instance, the average per timestep with doreisa - first, 
allocate your resources dinamically with `salloc`. 
Make sure to allocate a perfect square number of nodes + 1 (aka: 2, 5, 10, 17, etc.).

Then, simply run 
```
bash ~/paflow/bench-parflow/scripts/run/leonardo/start_multinode_doreisa.sh 0 <exp-id>
```

All run scripts take two arguments: 
- Arg1 (0 or 1): the analytics to run. 0 is for average per timestep, 1 is for derivative.
- Arg2 (int): a numerical ID for the experiment. Only relevant for benchmark purposes.

To run analytics using deisa, follow the same procedure but use `start_multinode_deisa_insitu.sh`. 


To run only parflow, without analytics use `start_multinode_parflow`. Only allocate a square number 
of nodes (without the +1).

## Bench 

To bench (doreisa), modify the desired parameters that define the configuration in `scripts/bench/leonardo/bench-doreisa.sh` . 
For example, the number of nodes, the time, etc.

Then submit the batch script as follows (necessary to properly analyze the files with out utilities).
```
sbatch -o "R-%x-%j-20250630111558.o" -e "R-%x-%j-20250630111558.e" scripts/bench/loenardo/bench-doreisa <exp_id>
```

This will run the experiment and put it in `./experimemnts-doreisa`. 

Each experiment will contain an `R-*.o` file which will have a lot of useful information. Other, parflow
specific log files are also included. 

Make sure to keep the same experiment ID for same configurations to obtain some statistical averages.
By default, the bench will use the average per time step analytics. If you wish to change this, 
edit the script and change the 0 argument to a 1. 

