#!/bin/bash

BASE_ROOTDIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT_DIR=$BASE_ROOTDIR/scripts/run
BENCH_DIR=$BASE_ROOTDIR/scripts/bench
ITERATION=3

#SETUP ENVIRONMENT FOR SCRIPTS
eval "$(guix shell --preserve=OAR* --search-paths -m $BASE_ROOTDIR/env/guix/manifest-pip.scm)"
export GUIX_ENVIRONMENT="$(dirname $(printenv PATH | cut -d':' -f1))" #ugly but necessary
source $BASE_ROOTDIR/.venv/bin/activate

#CREATING RESULT FOLDER
if [[ ! -d $BENCH_DIR/results ]]; then
  echo "creating result folder : $BENCH_DIR/results"
  mkdir $BENCH_DIR/results
fi

echo "Starting bench for doreisa..."

#Adapted to Nancy gros cluster 36 max process
for ((i = 0; i < $ITERATION; i++)); do
  ray stop
  bash $SCRIPT_DIR/start_multinode_doreisa_avg.sh 6 5 >$BENCH_DIR/results/doreisa_avg_6_5_$(date +%Y%m%d_%H%M%S).o
  sleep 10
  pkill mpirun
  ray stop
  bash $SCRIPT_DIR/start_multinode_doreisa_derivative.sh 6 5 >$BENCH_DIR/results/doreisa_derivative_6_5_$(date +%Y%m%d_%H%M%S).o
  sleep 10
  pkill mpirun
done

#Move log file of every run in results folder
for filename in $BASE_ROOTDIR/clayL_*; do
  echo $filename
  LOG_FILE=$(basename ${filename})
  rm ${filename}/*.kinsol.*
  mv ${filename}/*.log $BENCH_DIR/results/${LOG_FILE}.log
done

ray stop
echo "Benchmark ended, result folder : $BENCH_DIR/results"

#CLEANING CLAYL FILES...
echo "Cleaning ClayL files... (exec $BENCH_DIR/clean_clay.sh"

rm -rf ~/bench-parflow/clayL_*
