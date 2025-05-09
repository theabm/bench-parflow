#!/bin/bash

# DOREISA MULTINODE

set -xeu

# --------------------------------------------------------
# 		NODE & RESOURCE ALLOCATION
# --------------------------------------------------------

# Get unique nodes
NODES=($(cat "$OAR_NODE_FILE" | uniq))
echo NODES: "${NODES[@]}"

# count number of nodes ( @ expands array, # counts elems)
TOTAL_NODES=${#NODES[@]}
echo TOTAL_NODES: "$TOTAL_NODES"

# Assign nodes based on given constraints
HEAD_NODE=${NODES[0]}             # First node for Ray Head Node
REMAINING_NODES=("${NODES[@]:1}") # Exclude scheduler node
N_REMAINING_NODES=${#REMAINING_NODES[@]}

PORT=4242
HEAD_ADDRESS=${HEAD_NODE}:$PORT
echo HEAD NODE "${HEAD_NODE}"
echo REMAINING NODES "${REMAINING_NODES[*]}"
echo N_REMAINING NODES "${N_REMAINING_NODES}"
echo HEAD_ADDRESS "${HEAD_ADDRESS}"

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

DOREISA_DIR=${BASE_ROOTDIR}/doreisa
export PYTHONPATH=$DOREISA_DIR

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
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-doreisa.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

# -------------------------------------------------------- Time measurement
# --------------------------------------------------------
start=$(date +%s)

# --------------------------------------------------------
# 			RAY HEAD NODE
# --------------------------------------------------------

mpirun -x PATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT --report-bindings \
  --host "${HEAD_NODE}":1 ray start --head --port=$PORT
end=$(date +%s)
echo Ray Head node started at $(expr $end - $start) seconds.
sleep 10

# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

end=$(date +%s)
ANALYTICS_START=$(expr $end - $start)
echo Launching Analytics at $ANALYTICS_START seconds.
export LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib

mpirun -x PYTHONPATH -x VIRTUAL_ENV -x VIRTUAL_ENV_PROMPT -x LD_LIBRARY_PATH \
  --report-bindings --host ${HEAD_NODE}:1 \
  bash -c "source $BASE_ROOTDIR/.venv/bin/activate && python3 $BASE_ROOTDIR/analytics/pressure-doreisa-derivative.py" \
  2>./errors/pressure-doreisa.e &

sleep 15

ANALYTICS_PID=$!
echo AnalyticsPID $ANALYTICS_PID

# --------------------------------------------------------
# 	                    SIMULATION
# --------------------------------------------------------

echo Launching Simulation...

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} ${nodes} ${cells}

# ray start and connect to head node
mpirun --host $(printf "%s:1," "${REMAINING_NODES[@]}" | sed 's/,$//') \
  bash -c "export GUIX_PROFILE=$PROFILE && source $PROFILE/etc/profile && source $BASE_ROOTDIR/.venv/bin/activate && ray start --address ${HEAD_ADDRESS} --num-cpus=2 &"

end=$(date +%s)
echo ray started and connected to head node at $(expr $end - $start) seconds.
sleep 20

mpirun -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib -x PYTHONPATH --host $(printf "%s:$MPI_PROCESSES," "${REMAINING_NODES[@]}" | sed 's/,$//') \
  bash -c "export GUIX_PROFILE=$PROFILE && source $PROFILE/etc/profile && source $BASE_ROOTDIR/.venv/bin/activate && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
  2>./errors/simulation.e

end=$(date +%s)
echo Simulation Finished! at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 		WAIT FOR PROCESSES TO FINISH
# --------------------------------------------------------
echo "Waiting on analytics.."
end=$(date +%s)
wait $ANALYTICS_PID
echo "Analytics Finished!"

cd "$OLDPWD"
echo "Cleaning up.."
set +xeu
