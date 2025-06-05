#!/usr/bin/env bash

set -xeu

# Base root dir of project
export BASE_ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

# where parflow-pdi is downloaded
export PF_DIR=${BASE_ROOTDIR}/parflow-pdi  

# Build PDI
source ${BASE_ROOTDIR}/scripts/build/build-pdi.sh

# Build Deisa and DoReisa
source ${BASE_ROOTDIR}/scripts/build/build-python-deps.sh

# Build Parflow
source ${BASE_ROOTDIR}/scripts/build/build-parflow.sh

set +xeu
