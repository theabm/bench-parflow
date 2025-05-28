#!/bin/bash

set -xe

export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_DIR=/etc/ssl/certs

BASE_ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

TCL_PATH=$(which tclsh8.6)

PDIV=1.8.3
PDI_DIR=${BASE_ROOTDIR}/pdi-$PDIV
PDI_INSTALL=$PDI_DIR/install

PF_DIR=${BASE_ROOTDIR}/parflow-pdi

#-------------------------------Parflow-PDI-----------------------------------------

if [ ! -d "$PF_DIR" ]; then
  echo "Downloading Parflow..."
  git clone git@github.com:theabm/parflow-insitu.git "$PF_DIR"
fi

# build and install
export CC=mpicc
export CXX=mpicxx
export FC=mpif90

rm -rf "$PF_DIR"/build "$PF_DIR"/install
mkdir "$PF_DIR"/install

if [ -n "${GUIX_ENVIRONMENT}" ]; then
    NETCDF_PATH=$(nc-config --prefix)
elif [ -n "${SPACK_ENV}" ]; then
    NETCDF_PATH="$(spack location -i netcdf-c)"
else
    echo "No environment detected. Please set GUIX_ENVIRONMENT or SPACK_ENV. Many scripts might fail."
fi

echo "Building Parflow..."

cmake -DCMAKE_INSTALL_PREFIX="$PF_DIR"/install \
  -DPARFLOW_HAVE_CLM=ON \
  -DPARFLOW_AMPS_LAYER=mpi1 \
  -DTCL_TCLSH=$TCL_PATH \
  -DPDI_ROOT=$PDI_INSTALL \
  -DNETCDF_DIR=$NETCDF_PATH \
  -DPARFLOW_ENABLE_HDF5=TRUE \
  -DPARFLOW_AMPS_SEQUENTIAL_IO=on \
  -DPARFLOW_ENABLE_TIMING=TRUE \
  -DCMAKE_BUILD_TYPE=Release \
  -DPARFLOW_ENABLE_SLURM=TRUE \
  -S "$PF_DIR" -B "$PF_DIR"/build

make -C "$PF_DIR"/build -j $(nproc)
make -C "$PF_DIR"/build install

if [ $? -eq 0 ]; then
  echo "Parflow installed sucessfully!"
else
  echo "Parflow installation failed!"
fi

set +xe
