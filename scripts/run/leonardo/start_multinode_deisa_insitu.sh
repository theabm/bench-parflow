#!/usr/bin/env bash

set -xeu

echo RUNNING: DEISA

if [[ "$#" -lt 2 ]]; then
  echo "Error: A case (0 or 1) and a configuration ID (0 - N) must be provided as arguments."
  exit 1
fi

if [[ "$1" == "0" ]]; then
  APP="avg"
elif [[ "$1" == "1" ]]; then
  APP="derivative"
elif [[ "$1" == "2" ]]; then
  APP="toy"
else
  echo "Error: Argument must be either 0 or 1."
  exit 1
fi


# --------------------------------------------------------
# 		NODE & RESOURCE ALLOCATION
# --------------------------------------------------------

# Get unique nodes
NODES_STRING=$(scontrol show hostnames $SLURM_JOB_NODELIST)
echo NODES: "${NODES_STRING[@]}"

readarray -t NODES <<< "$NODES_STRING"

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

N_SIM_NODES=${#SIM_NODES[@]}
echo HEAD_NODE "$HEAD_NODE"
echo SIM_NODES "${SIM_NODES[*]}"
echo N_SIM_NODES "${N_SIM_NODES}"

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

DEISA_DIR=${BASE_ROOTDIR}/deisa
export PYTHONPATH=$DEISA_DIR
SCHEFILE=scheduler.json

CASE_NAME="clayL"
xsplit=10 # Number of MPI tasks per node along the x-axis
ysplit=10 # Number of MPI tasks per node along the y-axis

cells=240 # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$N_SIM_NODES
# HEAD NODE
DASK_SCHEDULER_CPUS=55
ANALYTICS_CPUS=56
MEM_LOG_CPUS=1
# ----
# SUM: 112

# SIM NODES
DASK_WORKER_CPUS=11
MPI_PROCESSES=$((xsplit * ysplit))
# MEM_LOG_CPUS
# ----
# SUM: 112

CONFIG_ID=$2
EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_$(date +%Y%m%d_%H%M%S)_$CONFIG_ID"
mkdir -p "$EXP_DIR"
echo "CONFIG_ID : $CONFIG_ID"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-deisa-insitu.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

if ! [ -f $BASE_ROOTDIR/utils/time-offset.out ]; then
  mpicc $BASE_ROOTDIR/utils/time-offset.c -o $BASE_ROOTDIR/utils/time-offset.out
fi

srun --overlap --ntasks-per-node=1 --cpus-per-task=1 bash -c "
  $BASE_ROOTDIR/utils/time-offset.out
"

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

#if [ ! -n "${SPACK_ENV}" ]; then
cat > "./activate_env.sh" << 'EOF'
#!/usr/bin/env bash

source $BASE_ROOTDIR/../spack/share/spack/setup-env.sh

SPACK_ENV=$BASE_ROOTDIR/env/spack
spack env activate $SPACK_ENV
EOF

source ./activate_env.sh
#else
#    echo "No environment detected. Please set GUIX_ENVIRONMENT or SPACK_ENV. Many scripts might fail."
#fi

# --------------------------------------------------------
# 			DASK SCHEDULER
# --------------------------------------------------------

# Start memory logger on every node - cpu 0 and 1 is dedicated only to this
srun --cpu-bind=verbose,core --ntasks-per-node=1 --cpus-per-task=$MEM_LOG_CPUS \
	python3 $BASE_ROOTDIR/utils/memory-logger.py --interval 30 &

echo "Launching Dask Scheduler on ${HEAD_NODE}..."
srun --cpu-bind=verbose,core --nodes=1 --nodelist=$HEAD_NODE --ntasks=1 --cpus-per-task=$DASK_SCHEDULER_CPUS \
	dask scheduler --scheduler-file ./$SCHEFILE 2>./errors/scheduler.e &

# Wait for the scheduler file to be created
while ! [ -f $SCHEFILE ]; do
  sleep 3
done

end=$(date +%s)
echo Dask Scheduler Launched at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

end=$(date +%s)
ANALYTICS_START=$(expr "$end" - "$start")
echo Launching Analytics at "$ANALYTICS_START" seconds.

srun --cpu-bind=verbose,core --nodes=1 --nodelist=$HEAD_NODE --ntasks=1 --cpus-per-task=$ANALYTICS_CPUS \
  	bash -c "
	python3 $BASE_ROOTDIR/analytics/pressure-deisa-insitu-$APP.py $N_SIM_NODES $SCHEFILE $MPI_PROCESSES $EXP_DIR \
 " 2>./errors/pressure-deisa.e &


ANALYTICS_PID=$!
echo "AnalyticsPID $ANALYTICS_PID"

# --------------------------------------------------------
# 				DASK WORKERS
# --------------------------------------------------------

echo "Launching Dask Workers on ${#SIM_NODES[@]} nodes..."
# One Dask Worker per node
srun --cpu-bind=verbose,core --nodes=$N_SIM_NODES -x $HEAD_NODE \
	--ntasks=$N_SIM_NODES --ntasks-per-node=1 --cpus-per-task=$DASK_WORKER_CPUS\
	bash -c "
	dask worker --worker-port 2000 --scheduler-file ./$SCHEFILE \
	--local-directory ./workers --nworkers 1 --nthreads $DASK_WORKER_CPUS \
" 2>./errors/dask-workers.e &

end=$(date +%s)
echo Dask Workers Launched! at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 			SIMULATION
# --------------------------------------------------------


CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} "${nodes}" ${cells}

srun --cpu-bind=verbose,core --ntasks=$((MPI_PROCESSES * N_SIM_NODES)) --nodes=$N_SIM_NODES -x $HEAD_NODE \
	--ntasks-per-node=$MPI_PROCESSES --cpus-per-task=1\
	bash -c "
       ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE} \
"  2>./errors/simulation.e

end=$(date +%s)
echo Simulation Finished! at $(expr $end - $start) seconds.

# --------------------------------------------------------
# 			WAIT FOR PROCESSES TO FINISH
# --------------------------------------------------------

echo "Waiting on analytics..."
wait $ANALYTICS_PID
end=$(date +%s)
echo "Analytics Finished!"
echo Execution time was $(expr $end - $start) seconds.

cd "$OLDPWD"
echo "Cleaning up..."

set +xeu
