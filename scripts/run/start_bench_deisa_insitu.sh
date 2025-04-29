#!/bin/bash

BASE_ROOTDIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT_DIR=$BASE_ROOTDIR/scripts/run
ITERATION=2

if [[ ! -d $SCRIPT_DIR/time_measurement ]]; then
  echo "creating result folder : $SCRIPT_DIR/time_measurement"
  mkdir $SCRIPT_DIR/time_measurement
fi

echo "Starting bench for deisa in situ..."

for ((i = 0; i < $ITERATION; i++)); do
  bash $SCRIPT_DIR/start_multinode_deisa_insitu.sh 6 | grep -v + >$SCRIPT_DIR/time_measurement/deisa_insitu_6_6_$i.o
done

echo "Benchmark ended, result folder : $SCRIPT_DIR/time_measurement"
echo "Cleaning ClayL files... (exec $BASE_ROOTDIR/clean_clay.sh"

bash $BASE_ROOTDIR/clean_clay.sh
