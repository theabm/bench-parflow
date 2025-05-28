#!/usr/bin/env bash

echo RUNNING: DEISA

if [[ "$#" -lt 1 ]]; then
  echo "Error: An argument (0 or 1) must be provided."
  exit 1
fi

if [[ "$1" == "0" ]]; then
  APP="avg"
elif [[ "$1" == "1" ]]; then
  APP="derivative"
else
  echo "Error: Argument must be either 0 or 1."
  exit 1
fi

set -xeu

# --------------------------------------------------------
# 		NODE & RESOURCE ALLOCATION
# --------------------------------------------------------

# Get unique nodes
NODES=($(cat $OAR_NODE_FILE | uniq))
echo NODES: "${NODES[@]}"

# count number of nodes ( @ expands array, # counts elems)
TOTAL_NODES=${#NODES[@]}
echo TOTAL_NODES: "$TOTAL_NODES"

if [[ $TOTAL_NODES -eq 1 ]]; then
  echo "Running with only one node."

  # head node and sim nodes are the same
  HEAD_NODE=${NODES[0]} 
  SIM_NODES=("${NODES[@]:0}") 
  N_SIM_NODES=${#SIM_NODES[@]}
else
  echo "Running with more than one node."

  # head node is for scheduler and analytics
  HEAD_NODE=${NODES[0]}        

  # remaining nodes are for simulation
  SIM_NODES=("${NODES[@]:1}") 
  N_SIM_NODES=${#SIM_NODES[@]}
fi

echo HEAD_NODE "$HEAD_NODE"
echo SIM_NODES "${SIM_NODES[*]}"
echo N_SIM_NODES "${N_SIM_NODES}"

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
if [[ "$#" -eq 3 ]]; then
  xsplit=$2 # Number of MPI tasks per node along the x-axis
  ysplit=$3 # Number of MPI tasks per node along the y-axis
else
  xsplit=4 # Number of MPI tasks per node along the x-axis
  ysplit=4 # Number of MPI tasks per node along the y-axis
fi
cells=120 # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$N_SIM_NODES
MPI_PROCESSES=$((xsplit * ysplit))

EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EXP_DIR"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-deisa-insitu.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

HOST_FILE=$EXP_DIR/hostfile.txt

for node in "${SIM_NODES[@]}"; do
  for procs in $(seq 1 $MPI_PROCESSES); do
    echo "$node" >> "$HOST_FILE"
  done
done

HOST_FILE2=$EXP_DIR/hostfile2.txt

for node in "${SIM_NODES[@]}"; do
  echo "$node slots=$MPI_PROCESSES" >> "$HOST_FILE2"
done

# --------------------------------------------------------
# 			Time measurement
# --------------------------------------------------------
start=$(date +%s)

if [ -n "${SPACK_ENV}" ]; then
cat > "./activate_env.sh" << 'EOF'
#!/usr/bin/env bash

source $1/spack/share/spack/setup-env.sh

SPACK_ENV=$1/env/spack
spack env activate $SPACK_ENV
EOF
else
    echo "No environment detected. Please set GUIX_ENVIRONMENT or SPACK_ENV. Many scripts might fail."
fi
# --------------------------------------------------------
# 			DASK SCHEDULER
# --------------------------------------------------------

echo "Launching Dask Scheduler on ${HEAD_NODE}..."
mpirun --host "${HEAD_NODE}":1 bash -c "source ./activate_env.sh $BASE_ROOTDIR && dask scheduler --scheduler-file ./$SCHEFILE 2>./errors/scheduler.e" &

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

mpirun --host "${HEAD_NODE}":1 bash -c "source ./activate_env.sh $BASE_ROOTDIR \
 && python3 $BASE_ROOTDIR/analytics/pressure-deisa-insitu-$APP.py $N_SIM_NODES $SCHEFILE $MPI_PROCESSES $EXP_DIR " \
  2>./errors/pressure-deisa.e &

ANALYTICS_PID=$!
echo "AnalyticsPID $ANALYTICS_PID"

# --------------------------------------------------------
# 				DASK WORKERS
# --------------------------------------------------------

echo "Launching Dask Workers on ${#SIM_NODES[@]} nodes..."

# One Dask Worker per node
mpirun --host $(printf "%s:1," "${SIM_NODES[@]}" | sed 's/,$//') \
  bash -c "source ./activate_env.sh $BASE_ROOTDIR \
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

mpirun -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib -x BASE_ROOTDIR -x PYTHONPATH\
  --report-bindings --hostfile "$HOST_FILE2" \
  bash -c "source ./activate_env.sh $BASE_ROOTDIR && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
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
