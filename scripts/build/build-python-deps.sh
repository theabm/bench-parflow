#!/usr/bin/env bash

set -xeu

BASE_ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

DEISA_DIR=${BASE_ROOTDIR}/deisa
DOREISA_DIR=${BASE_ROOTDIR}/doreisa
export PYTHONPATH=$DEISA_DIR:$DOREISA_DIR

#-------------------------------Deisa-----------------------------------------

if [ ! -d "$DEISA_DIR" ];then
	echo "Downloading Deisa..."
	# checkout the support_contracts_and_annotations branch which contains the latest changes
	git clone -b support_contracts_and_annotations https://github.com/pdidev/deisa.git "$DEISA_DIR"
else
	echo "Deisa already exists."
fi

#-------------------------------DoReisa-----------------------------------------


if [ ! -d "$DOREISA_DIR" ];then
	echo "Downloading doreisa..."
	# checkout the v0.1.1 tag which contains the latest stable release
	git clone -b v0.1.1 https://github.com/AdrienVannson/doreisa.git "$DOREISA_DIR"
else
	echo "Doreisa already exists."
fi
set +xeu
