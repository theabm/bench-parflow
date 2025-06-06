#!/usr/bin/env bash

set -xeu

# --------------------------------------------------------
# 		NODE & RESOURCE ALLOCATION
# --------------------------------------------------------

# Get unique nodes
NODES_STRING=$(scontrol show hostnames $SLURM_JOB_NODELIST)
echo NODES: "${NODES_STRING[@]}"

readarray -t NODES <<< "$NODES_STRING"
echo NODES: "${NODES[@]}"

# count number of nodes ( @ expands array, # counts elems)
TOTAL_NODES=${#NODES[@]}
echo TOTAL_NODES: "$TOTAL_NODES"

# --------------------------------------------------------
# 				ENVIRONMENT SETUP
# --------------------------------------------------------

# Update BASE_ROOTDIR to point to the root of the project
OLDPWD=$(pwd)
BASE_ROOTDIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)

export OMP_PROC_BIND=spread
export OMP_PLACES=cores

export PF_DIR=$BASE_ROOTDIR/parflow-pdi
export PARFLOW_DIR=$PF_DIR/install

PDIV=1.8.3
export PDI_INSTALL=${BASE_ROOTDIR}/pdi-$PDIV/install

echo Launching Simulation...

CASE_NAME="clayL"
xsplit=5  # Number of MPI tasks per node along the x-axis
ysplit=5  # Number of MPI tasks per node along the y-axis
cells=240  # Total number of cells along each dimension per node (square problem in x and y dimensions)
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

cat > "./activate_env.sh" << 'EOF'
#!/usr/bin/env bash

source $1/../spack/share/spack/setup-env.sh

SPACK_ENV=$1/env/spack
spack env activate $SPACK_ENV
EOF

# Start memory logger on every node - cpu 0 and 1 is dedicated only to this
srun --cpu-bind=verbose,core --ntasks-per-node=1 --cpus-per-task=2 bash -c "
    source ./activate_env.sh $BASE_ROOTDIR
    python3 $BASE_ROOTDIR/utils/memory-logger.py --interval 30 
"&

srun --cpu-bind=verbose,core  --nodes=$TOTAL_NODES \
	--ntasks-per-node=$MPI_PROCESSES --cpus-per-task=1 \
  	bash -c "
		source ./activate_env.sh $BASE_ROOTDIR 
		${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}
	" 2>./errors/simulation.e

echo Simulation Finished!

cd "$OLDPWD"
set +xeu
