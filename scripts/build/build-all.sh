#!/bin/bash

# before running make sure environment is set by running:
# guix shell --pure -m manifest-pip.scm 
# then activate the .venv using
# source .venv/bin/activate

set -xue

# needed because pure guix shell does not set these
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_DIR=/etc/ssl/certs

# Base root dir of project
export BASE_ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

# where parflow-pdi is downloaded
export PF_DIR=${BASE_ROOTDIR}/parflow-pdi  

# where tcl is installed through Guix
TCL_PATH=$(which tclsh8.6)

# Build PDI
source ${BASE_ROOTDIR}/scripts/build/build-pdi.sh

# Build Deisa and DoReisa
source ${BASE_ROOTDIR}/scripts/build/build-python.sh

# Build Parflow
source ${BASE_ROOTDIR}/scripts/build/build-parflow.sh

set +xeu
