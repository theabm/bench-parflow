#!/usr/bin/env bash

set -xeu

if [[ "$#" -lt 1 ]]; then
  echo "Error: A configuration ID (0 - N) must be provided as arguments."
  exit 1
fi

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
ysplit=6  # Number of MPI tasks per node along the y-axis
cells=240  # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$TOTAL_NODES
MPI_PROCESSES=$((xsplit * ysplit))

if ! [ -f $BASE_ROOTDIR/utils/time-offset.out ]; then
  mpicc $BASE_ROOTDIR/utils/time-offset.c -o $BASE_ROOTDIR/utils/time-offset.out
fi

CONFIG_ID=$2
EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_$(date +%Y%m%d_%H%M%S)_$CONFIG_ID"
echo "CONFIG_ID : $CONFIG_ID"
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

SPACK_ENV=$1/../parflow-env
spack env activate $SPACK_ENV
EOF

#srun --overlap --ntasks-per-node=1 --cpus-per-task=1 bash -c "
#  $BASE_ROOTDIR/utils/time-offset.out
#" 2>./errors/time-offset.e
#
## Start memory logger on every node - cpu 0 and 1 is dedicated only to this
#srun --cpu-bind=verbose,core --ntasks-per-node=1 --cpus-per-task=1 bash -c "
#    export OMPI_MCA_btl_tcp_if_include="ib0"
#    source ./activate_env.sh $BASE_ROOTDIR
#    python3 $BASE_ROOTDIR/utils/memory-logger.py --interval 30 
#"&

srun --nodes=$TOTAL_NODES \
     --cpu-bind=verbose,core \
     --ntasks-per-node=$MPI_PROCESSES \
     --cpus-per-task=1 \
     bash -c "
	source ./activate_env.sh $BASE_ROOTDIR 
	${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}
     " 2>./errors/simulation.e

echo Simulation Finished!

cd "$OLDPWD"
set +xeu
