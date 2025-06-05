#!/usr/bin/env bash 

set -xeu

echo RUNNING: DOREISA

if [[ "$#" -lt 1 ]]; then
  echo "Error: An argument (0 or 1) must be provided."
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
NODES=($(cat "$OAR_NODE_FILE" | uniq))
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
cp "$PF_DIR"/pfsimulator/third_party/pdi/conf-doreisa.yml "$EXP_DIR"/conf.yml
cp "$BASE_ROOTDIR"/scripts/run/clayL.tcl "$EXP_DIR"/clayL.tcl
mkdir ./errors

# -------------------------------------------------------- Time measurement
# --------------------------------------------------------
start=$(date +%s)

if [ -n "${SPACK_ENV}" ]; then
cat > "./activate_env.sh" << 'EOF'
#!/usr/bin/env bash

source $1/../spack/share/spack/setup-env.sh

SPACK_ENV=$1/env/spack
spack env activate $SPACK_ENV
EOF
else
    echo "No environment detected. Please set GUIX_ENVIRONMENT or SPACK_ENV. Many scripts might fail."
fi

# --------------------------------------------------------
# 			RAY HEAD NODE
# --------------------------------------------------------

mpirun --host "${HEAD_NODE}":1 bash -c "source ./activate_env.sh $BASE_ROOTDIR && ray start --head --port=$PORT"
end=$(date +%s)
echo Ray Head node started at $(expr $end - $start) seconds.
sleep 10
# --------------------------------------------------------
# 				ANALYTICS
# --------------------------------------------------------

end=$(date +%s)
ANALYTICS_START=$(expr "$end" - "$start")
echo Launching Analytics at "$ANALYTICS_START" seconds.

mpirun --host "${HEAD_NODE}":1 bash -c "source ./activate_env.sh $BASE_ROOTDIR \
 && python3 $BASE_ROOTDIR/analytics/pressure-doreisa-$APP.py" \
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

if [ "$TOTAL_NODES" -gt 1 ]; then
  # ray start and connect to head node
  mpirun --host $(printf "%s:1," "${SIM_NODES[@]}" | sed 's/,$//') \
  bash -c "source ./activate_env.sh $BASE_ROOTDIR && ray start --address ${HEAD_ADDRESS} --num-cpus=2 &"

  end=$(date +%s)
  echo ray started and connected to head node at $(expr $end - $start) seconds.
  sleep 20
fi

mpirun -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib -x BASE_ROOTDIR -x PYTHONPATH\
  --host $(printf "%s:$MPI_PROCESSES," "${SIM_NODES[@]}" | sed 's/,$//') \
  bash -c "source ./activate_env.sh $BASE_ROOTDIR && ${PDI_INSTALL}/bin/pdirun ${PARFLOW_DIR}/bin/parflow ${CASE}" \
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
