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
  bash $SCRIPT_DIR/start_multinode_doreisa.sh 6 >$BENCH_DIR/results/doreisa_6_6_${i}_$(date +%Y%m%d_%H%M%S).o
  sleep 10
  pkill mpirun
done

#CLEANING CLAYL FILES...
echo "Benchmark ended, result folder : $BENCH_DIR/results"
#echo "Cleaning ClayL files... (exec $BENCH_DIR/clean_clay.sh"

rm -rf ~/bench-parflow/clayL_*
