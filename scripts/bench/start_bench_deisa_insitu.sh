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

echo "Starting bench for deisa in situ..."

#Adapted to Nancy gros cluster 36 max process
for ((i = 0; i < $ITERATION; i++)); do
  pkill dask
  bash $SCRIPT_DIR/start_multinode_deisa_insitu.sh 6 >$BENCH_DIR/results/deisa_insitu_6_6_$i.o
  #bash $SCRIPT_DIR/start_multinode_deisa_insitu.sh 4 | grep -v + >$BENCH_DIR/results/deisa_insitu_4_4_$i.o
  #bash $SCRIPT_DIR/start_multinode_deisa_insitu.sh 2 | grep -v + >$BENCH_DIR/results/deisa_insitu_2_2_$i.o
done

#CLEANING CLAYL FILES...
echo "Benchmark ended, result folder : $BENCH_DIR/results"
echo "Cleaning ClayL files... (exec $BENCH_DIR/clean_clay.sh"

bash $BENCH_DIR/clean_clay.sh
