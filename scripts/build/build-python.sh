#!/bin/bash

set -xue

export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_DIR=/etc/ssl/certs

BASE_ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

DEISA_DIR=${BASE_ROOTDIR}/deisa
DOREISA_DIR=${BASE_ROOTDIR}/doreisa
export PYTHONPATH=$DEISA_DIR:$DOREISA_DIR

#-------------------------------Deisa-----------------------------------------

if [ ! -d "$DEISA_DIR" ];then
	echo "Downloading Deisa..."
	git clone -b support_contracts_and_annotations https://github.com/pdidev/deisa.git "$DEISA_DIR"
else
	echo "Deisa already exists."
fi

#-------------------------------DoReisa-----------------------------------------


if [ ! -d "$DOREISA_DIR" ];then
	echo "Downloading doreisa..."
	git clone https://github.com/AdrienVannson/doreisa.git "$DOREISA_DIR"
else
	echo "doreisa already exists."
fi