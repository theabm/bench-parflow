#!/bin/bash

echo RUNNING: DEISA

set -xeu

# --------------------------------------------------------
# 		NODE & RESOURCE ALLOCATION
# --------------------------------------------------------

# Get unique nodes
NODES=($(cat $OAR_NODE_FILE | uniq))
echo NODES: "${NODES[@]}"

# count number of nodes ( @ expands array, # counts elems)
TOTAL_NODES=${#NODES[@]}
echo TOTAL_NODES: $TOTAL_NODES

# Ensure at least 3 nodes are available
if [[ $TOTAL_NODES -lt 3 ]]; then
    echo "Error: At least 3 nodes are required for this script to run."
    exit 1
fi

# Assign nodes based on given constraints
SCHEDULER_NODE=${NODES[0]}  # First node for Dask scheduler
REMAINING_NODES=("${NODES[@]:1}")  # Exclude scheduler node
N_REMAINING_NODES=${#REMAINING_NODES[@]}
echo SCHEDULER+CLIENT NODE ${SCHEDULER_NODE}
echo REMAINING NODES ${REMAINING_NODES[@]}
echo N_REMAINING NODES "${N_REMAINING_NODES}"

# Split remaining nodes into two equal groups
HALF_COUNT=$(( (${#REMAINING_NODES[@]} + 1) / 2 ))  # Rounds up if odd

SIM_NODES=("${REMAINING_NODES[@]:0:$HALF_COUNT}")  # First half for Sim
N_SIM_NODES=${#SIM_NODES[@]}
DASK_NODES=("${REMAINING_NODES[@]:$HALF_COUNT}")  # Second half for Dask
N_DASK_NODES=${#DASK_NODES[@]}

echo DASK_NODES: ${DASK_NODES[@]}
echo N_DASK_NODES: $N_DASK_NODES
echo SIMULATION_NODES: ${SIM_NODES[@]}
echo N_SIM_NODES: $N_SIM_NODES

# --------------------------------------------------------
# 				ENVIRONMENT SETUP
# --------------------------------------------------------

# Update BASE_ROOTDIR to point to the root of the project
OLDPWD=$(pwd)
BASE_ROOTDIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)

export OMP_PROC_BIND=spread
export OMP_PLACES=cores

export PF_DIR=$BASE_ROOTDIR/parflow-pdi
export PARFLOW_DIR=$PF_DIR/install

PDIV=1.8.3
export PDI_INSTALL=${BASE_ROOTDIR}/pdi-$PDIV/install

DEISA_DIR=${BASE_ROOTDIR}/deisa
export PYTHONPATH=$DEISA_DIR
SCHEFILE=scheduler.json


CASE_NAME="clayL"
xsplit=4  # Number of MPI tasks per node along the x-axis
ysplit=4  # Number of MPI tasks per node along the y-axis
cells=120  # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$N_SIM_NODES
MPI_PROCESSES=$((xsplit * ysplit))

EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EXP_DIR"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-deisa.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

# --------------------------------------------------------
# 			DASK SCHEDULER
# --------------------------------------------------------

echo "Launching Dask Scheduler on ${SCHEDULER_NODE}..."
mpirun -x PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT --report-bindings \
       --host ${SCHEDULER_NODE}:1 dask scheduler --scheduler-file ./$SCHEFILE 2>./errors/scheduler.e &

# Wait for the scheduler file to be created
while ! [ -f $SCHEFILE ]; do
    sleep 3
done

echo "Dask Scheduler Launched!"

# --------------------------------------------------------
# 				DASK WORKERS
# --------------------------------------------------------

echo "Launching Dask Workers on ${#DASK_NODES[@]} nodes..."

# One Dask Worker per node
mpirun -x PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT --report-bindings \
    --host $(printf "%s:1," "${DASK_NODES[@]}" | sed 's/,$//') \
    bash -c 'dask worker --scheduler-file '"./$SCHEFILE"' \
    --local-directory '"./workers"' \
    --nworkers 1 \
    --nthreads $(nproc) 2>./errors/dask-workers.e' &

WORK_PID=$!
echo "Dask Workers Launched!"

# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

echo "Launching Analytics..."
export LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib
mpirun -x PYTHONPATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT -x LD_LIBRARY_PATH --report-bindings --host ${SCHEDULER_NODE}:1 python3 $BASE_ROOTDIR/analytics/pressure-deisa.py $N_DASK_NODES $SCHEFILE 2>./errors/pressure-deisa.e &

ANALYTICS_PID=$!
echo "AnalyticsPID $ANALYTICS_PID"

# --------------------------------------------------------
# 				SIMULATION
# --------------------------------------------------------

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} ${nodes} ${cells}

export LD_LIBRARY_PATH=${PDI_INSTALL}/lib
mpirun -x BASE_ROOTDIR -x PYTHONPATH -x LD_LIBRARY_PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT \
       --host $(printf "%s:$MPI_PROCESSES," "${SIM_NODES[@]}" | sed 's/,$//') \
       bash -c "source $BASE_ROOTDIR/.venv/bin/activate && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
       2>./errors/simulation.e

echo "Simulation Finished!"

# --------------------------------------------------------
# 				WAIT FOR PROCESSES TO FINISH
# --------------------------------------------------------

echo "Waiting on analytics..."
wait $ANALYTICS_PID
echo "Analytics Finished!"

cd "$OLDPWD"
echo "Cleaning up..."

set +xeu
