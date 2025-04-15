#!/bin/bash

echo RUNNING: DEISA

set -xeu

N_DASKWORKERS=2

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
nodes=1
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

echo Launching Dask Scheduler... 
dask scheduler --scheduler-file ./$SCHEFILE 2>./errors/dask-scheduler.e&

# Wait for the SCHEFILE to be created 
while ! [ -f $SCHEFILE ]; do
    sleep 3
done

echo Dask Scheduler Launched!

# --------------------------------------------------------
# 				DASK WORKERS
# --------------------------------------------------------

echo Launching Dask Workers...

dask worker --scheduler-file ./$SCHEFILE --local-directory ./workers  --nworkers $N_DASKWORKERS  --nthreads 1 2>./errors/dask-workers.e &

WORK_PID=$!

echo Dask Workers Launched!

# --------------------------------------------------------
# 			ANALYTICS
# --------------------------------------------------------

echo Launching Analytics...
LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib python3 $BASE_ROOTDIR/analytics/pressure-deisa.py $N_DASKWORKERS $SCHEFILE 2>./errors/pressure-deisa.e & 

ANALYTICS_PID=$!
echo AnalyticsPID $ANALYTICS_PID

# --------------------------------------------------------
# 				SIMULATION
# --------------------------------------------------------

CASE=${CASE_NAME}_${xsplit}_${ysplit}_${nodes}_${cells}
tclsh ${CASE_NAME}.tcl ${xsplit} ${ysplit} ${nodes} ${cells}

LD_LIBRARY_PATH=${PDI_INSTALL}/lib "${PDI_INSTALL}"/bin/pdirun mpirun --verbose -n $MPI_PROCESSES "${PARFLOW_DIR}"/bin/parflow ${CASE} 2>./errors/simulation.e

echo Simulation Finished!

# --------------------------------------------------------
# 		WAIT FOR PROCESSES TO FINISH
# --------------------------------------------------------

echo "Waiting on analytics.."
wait $ANALYTICS_PID
echo "Analytics Finished!"

cd "$OLDPWD"
echo "Cleaning up.."
set +xeu
