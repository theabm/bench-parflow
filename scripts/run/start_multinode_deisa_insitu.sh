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
if [[ $TOTAL_NODES -lt 2 ]]; then
  echo "Error: At least 2 nodes are required for this script to run."
  exit 1
fi

# Assign nodes based on given constraints
SCHEDULER_NODE=${NODES[0]}        # First node for Dask scheduler
REMAINING_NODES=("${NODES[@]:1}") # Exclude scheduler node
N_REMAINING_NODES=${#REMAINING_NODES[@]}

echo SCHEDULER NODE "$SCHEDULER_NODE"
echo REMAINING NODES "${REMAINING_NODES[*]}"
echo N_REMAINING NODES "${N_REMAINING_NODES}"

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

PROFILE=$BASE_ROOTDIR/env/guix/profile

CASE_NAME="clayL"
if [[ "$#" -eq 2 ]]; then
  xsplit=$1 # Number of MPI tasks per node along the x-axis
  ysplit=$2 # Number of MPI tasks per node along the y-axis
else
  xsplit=4 # Number of MPI tasks per node along the x-axis
  ysplit=4 # Number of MPI tasks per node along the y-axis
fi
cells=240 # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$N_REMAINING_NODES
MPI_PROCESSES=$((xsplit * ysplit))

EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EXP_DIR"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-deisa-insitu.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

HOST_FILE="./hostfile.txt"

for node in "${REMAINING_NODES[@]}"; do
  for procs in $(seq 1 $MPI_PROCESSES); do
    echo "$node" >>$HOST_FILE
  done
done

# --------------------------------------------------------
# 			Time measurement
# --------------------------------------------------------
start=$(date +%s)

# --------------------------------------------------------
# 			DASK SCHEDULER
# --------------------------------------------------------

echo "Launching Dask Scheduler on ${SCHEDULER_NODE}..."
mpirun -x PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT --report-bindings \
  --host "${SCHEDULER_NODE}":1 dask scheduler --scheduler-file ./$SCHEFILE 2>./errors/scheduler.e &

# Wait for the scheduler file to be created
while ! [ -f $SCHEFILE ]; do
  sleep 3
done

end=$(date +%s)
echo Dask Scheduler Launched at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

echo "Launching Analytics..."
export LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib

mpirun -x PYTHONPATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT -x LD_LIBRARY_PATH \
  --report-bindings --host "${SCHEDULER_NODE}":1 \
  bash -c "source $BASE_ROOTDIR/.venv/bin/activate \
 && python3 $BASE_ROOTDIR/analytics/pressure-deisa-insitu.py $N_REMAINING_NODES $SCHEFILE $MPI_PROCESSES $EXP_DIR " \
  2>./errors/pressure-deisa.e &

ANALYTICS_PID=$!
echo "AnalyticsPID $ANALYTICS_PID"

# --------------------------------------------------------
# 				DASK WORKERS
# --------------------------------------------------------

echo "Launching Dask Workers on ${#REMAINING_NODES[@]} nodes..."

# One Dask Worker per node
mpirun --host $(printf "%s:1," "${REMAINING_NODES[@]}" | sed 's/,$//') \
  bash -c "export GUIX_PROFILE=$PROFILE \
    && source $PROFILE/etc/profile \
    && source $BASE_ROOTDIR/.venv/bin/activate \
    && dask worker --worker-port 2000 --scheduler-file ./$SCHEFILE \
    --local-directory ./workers --nworkers 1 --nthreads 4" \
  2>./errors/dask-workers.e &

end=$(date +%s)
echo Dask Workers Launched! at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 				SIMULATION
# --------------------------------------------------------

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} "${nodes}" ${cells}

export LD_LIBRARY_PATH=${PDI_INSTALL}/lib
mpirun -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib -x BASE_ROOTDIR -x PYTHONPATH -x LD_LIBRARY_PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT \
  --hostfile $HOST_FILE \
  bash -c "source $BASE_ROOTDIR/.venv/bin/activate && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
  2>./errors/simulation.e

end=$(date +%s)
echo Simulation Finished! at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 				WAIT FOR PROCESSES TO FINISH
# --------------------------------------------------------

echo "Waiting on analytics..."
wait $ANALYTICS_PID
end=$(date +%s)
echo "Analytics Finished!"
echo Execution time was $(expr $end - $start) seconds.

cd "$OLDPWD"
echo "Cleaning up..."

set +xeu
