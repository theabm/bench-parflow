#!/bin/bash

set -xue

export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_DIR=/etc/ssl/certs

BASE_ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

PDIV=1.8.3
export PDI_DIR=${BASE_ROOTDIR}/pdi-$PDIV
export PDI_INSTALL=$PDI_DIR/install
export PDI_LIBS=$PDI_INSTALL/lib

# Download PDI
if [ ! -d "./pdi-$PDIV" ];then
	# note the release version 1.8.2
	echo "Downloading PDI..."
    wget https://github.com/pdidev/pdi/archive/refs/tags/$PDIV.tar.gz -P "$BASE_ROOTDIR"
	tar -xf "$BASE_ROOTDIR"/$PDIV.tar.gz -C $BASE_ROOTDIR 
    rm "$BASE_ROOTDIR"/$PDIV.tar.gz 
else
	echo "PDI directory already exists. Proceeding to rebuild."
fi

rm -rf "$PDI_DIR"/install "$PDI_DIR"/build
mkdir "$PDI_DIR"/install


echo "Building PDI..."
cmake -DPython3_EXECUTABLE="${BASE_ROOTDIR}"/.venv/bin/python3 \
 -DBUILD_DEISA_PLUGIN=ON -DBUILD_PYTHON=ON -DBUILD_PYCALL_PLUGIN=ON -DCMAKE_INSTALL_PREFIX="$PDI_DIR"/install \
 -DBUILD_BENCHMARKING=OFF -DBUILD_DECL_NETCDF_PLUGIN=OFF -DBUILD_FORTRAN=OFF -DBUILD_NETCDF_PARALLEL=OFF \
 -DBUILD_SET_VALUE_PLUGIN=OFF -DBUILD_USER_CODE_PLUGIN=OFF \
 -S "$PDI_DIR" -B "$PDI_DIR"/build

make -C "$PDI_DIR"/build -j $(nproc)
make -C "$PDI_DIR"/build install

if [ $? -eq 0 ]; then
        echo "PDI build sucessfull!"
else
        echo "Parflow build failed!"
fi

