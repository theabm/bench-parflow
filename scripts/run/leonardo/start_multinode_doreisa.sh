#!/usr/bin/env bash 

set -xeu

echo RUNNING: DOREISA

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
  echo "Run with at least 2 nodes"
  exit 1
else
  echo "Running with more than one node."

  # head node is for main ray actor and analytics
  HEAD_NODE=${NODES[0]}             

  # remaining nodes are for simulation
  SIM_NODES=("${NODES[@]:1}") 
  N_SIM_NODES=${#SIM_NODES[@]}
fi

PORT=4242
HEAD_ADDRESS=${HEAD_NODE}:$PORT
echo HEAD NODE "${HEAD_NODE}"
echo HEAD_ADDRESS "${HEAD_ADDRESS}"
echo SIM_NODES "${SIM_NODES[*]}"
echo N_SIM_NODES "${N_SIM_NODES}"



# --------------------------------------------------------
#			ENVIRONMENT SETUP
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

DOREISA_DIR=${BASE_ROOTDIR}/doreisa
export PYTHONPATH=$DOREISA_DIR

CASE_NAME="clayL"

xsplit=10 # Number of MPI tasks per node along the x-axis
ysplit=10 # Number of MPI tasks per node along the y-axis

cells=240 # Total number of cells along each dimension per node (square problem in x and y dimensions)
nodes=$N_SIM_NODES
# HEAD NODE
RAY_HEAD_CPUS=55
ANALYTICS_CPUS=56
MEM_LOG_CPUS=1
# ----
# SUM: 112

# SIM NODES
RAY_WORKER_CPUS=11
MPI_PROCESSES=$((xsplit * ysplit))
# MEM_LOG_CPUS
# ----
# SUM: 112

CONFIG_ID=$2
EXP_DIR=$BASE_ROOTDIR/"${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_$(date +%Y%m%d_%H%M%S)_$CONFIG_ID"
mkdir -p "$EXP_DIR"
echo "CONFIG_ID : $CONFIG_ID"
cd "$EXP_DIR"
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-doreisa.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

if ! [ -f $BASE_ROOTDIR/utils/time-offset.out ]; then
  mpicc $BASE_ROOTDIR/utils/time-offset.c -o $BASE_ROOTDIR/utils/time-offset.out
fi

srun --overlap --ntasks-per-node=1 --cpus-per-task=1 bash -c "
  $BASE_ROOTDIR/utils/time-offset.out
"

# -------------------------------------------------------- 
#			Time measurement
# --------------------------------------------------------
start=$(date +%s)

cat > "./activate_env.sh" << 'EOF'
#!/usr/bin/env bash

source $1/../spack/share/spack/setup-env.sh

SPACK_ENV=$1/env/spack
spack env activate $SPACK_ENV
EOF

# --------------------------------------------------------
# 			RAY HEAD NODE
# --------------------------------------------------------


# Find the IP of the head node. We use ib0 for the InfiniBand interface.
HEAD_NODE_IP=$(srun --overlap --nodes=1 --nodelist=$HEAD_NODE --ntasks-per-node=1 bash -c 'ip -o -4 addr show ib0 | awk "{print \$4}" | cut -d/ -f1')
echo "Head node IP: $HEAD_NODE_IP"

# Start memory logger on every node - cpu 0 and 1 is dedicated only to this
srun  --cpu-bind=verbose,core --ntasks-per-node=1 --cpus-per-task=$MEM_LOG_CPUS bash -c "
    source ./activate_env.sh $BASE_ROOTDIR
    python3 $BASE_ROOTDIR/utils/memory-logger.py --interval 30 
"&

# Start the head node -- will have 20 cores in the node
srun  --cpu-bind=verbose,core --nodes=1 --nodelist=$HEAD_NODE --ntasks=1 --cpus-per-task=$RAY_HEAD_CPUS bash -c "
    ulimit -n 65535
    export OPENBLAS_NUM_THREADS=1
    source ./activate_env.sh $BASE_ROOTDIR
    ray start --head --num-cpus=1 --node-ip-address=$HEAD_NODE_IP --port=$PORT --disable-usage-stats --block
" 2>./errors/ray-head.e &

end=$(date +%s)
echo Ray Head node started at $(expr $end - $start) seconds.

sleep 30
# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

end=$(date +%s)
ANALYTICS_START=$(expr "$end" - "$start")
echo Launching Analytics at "$ANALYTICS_START" seconds.

srun --cpu-bind=verbose,core  --nodes=1 --nodelist="${HEAD_NODE}" --ntasks=1 --cpus-per-task=$ANALYTICS_CPUS bash -c "
	source ./activate_env.sh $BASE_ROOTDIR
	python3 $BASE_ROOTDIR/analytics/pressure-doreisa-$APP.py
" 2>./errors/pressure-doreisa.e &

sleep 30

ANALYTICS_PID=$!
echo AnalyticsPID $ANALYTICS_PID

# --------------------------------------------------------
# 	                    SIMULATION
# --------------------------------------------------------

echo Launching Simulation...

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} ${nodes} ${cells}
NODELIST=$(printf "%s," "${SIM_NODES[@]}" | sed 's/,$//')

if [ "$TOTAL_NODES" -gt 1 ]; then
  # ray start and connect to head node
  srun --cpu-bind=verbose,core --nodes=$N_SIM_NODES \
  -x $HEAD_NODE --ntasks=$N_SIM_NODES --ntasks-per-node=1 --cpus-per-task=$RAY_WORKER_CPUS \
  bash -c "
  ulimit -n 65535
  export OMPI_MCA_btl_tcp_if_include="ib0"
  export OPENBLAS_NUM_THREADS=1
  node_ip=\$(ip -o -4 addr show ib0 | awk \"{print \\\$4}\" | cut -d/ -f1)
        echo \"Node IP: \$node_ip\"
  source ./activate_env.sh $BASE_ROOTDIR
  ray start --address ${HEAD_ADDRESS} --num-cpus=$RAY_WORKER_CPUS --node-ip-address=\$node_ip --block
 " 2>./errors/ray-workers.e &

  end=$(date +%s)
  echo ray started and connected to head node at $(expr $end - $start) seconds.
  sleep 30
fi

srun --cpu-bind=verbose,core  --nodes=$N_SIM_NODES -x $HEAD_NODE \
	--ntasks-per-node=$MPI_PROCESSES --cpus-per-task=1 \
  	bash -c "
		export OMPI_MCA_btl_tcp_if_include="ib0"
		source ./activate_env.sh $BASE_ROOTDIR 
		${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}
	" 2>./errors/simulation.e

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

## NEVER BEING CALLED BECAUSE DOREISA FOR NOW IS AN INFINITE WHILE LOOP SO WE NEED TO MANUALLY KILL THE CLUSTER
srun --nodes=1 --nodelist=$HEAD_NODE --ntasks=1  bash -c "
	ray status --address='127.0.0.1:4242'
" &

sleep 40

srun --nodes=1 --nodelist=$HEAD_NODE --ntasks=1  bash -c "
	ray stop
" &

sleep 10

set +xeu
