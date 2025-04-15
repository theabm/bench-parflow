#!/bin/bash

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

PROFILE=$BASE_ROOTDIR/env/guix/profile

echo Launching Simulation...

CASE_NAME="clayL"
xsplit=4  # Number of MPI tasks per node along the x-axis
ysplit=4  # Number of MPI tasks per node along the y-axis
cells=120  # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$TOTAL_NODES
MPI_PROCESSES=$((xsplit * ysplit))

EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EXP_DIR"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} "${nodes}" ${cells}

mpirun --host $(printf "%s:$MPI_PROCESSES," "${NODES[@]}" | sed 's/,$//') \
       bash -c "export GUIX_PROFILE=$PROFILE && source $PROFILE/etc/profile && source $BASE_ROOTDIR/.venv/bin/activate && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
       2>./errors/simulation.e

echo Simulation Finished!

cd "$OLDPWD"
set +xeu
