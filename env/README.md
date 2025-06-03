# Setting Up The Environment 

There main supported way to set up the environment is SPACK. 

The main testbed is G5K.

## Spack

To use spack, first clone the spack repo (one level above this project) and then activate spack.
``` bash
git clone https://github.com/spack/spack
cd spack 
. share/spack/setup-env.sh
```
To activate the environment use the following commands.

```bash
spack env activate root_of_repo/env/spack/
spack concretize -f 
spack install
```
To speed up the installation:

```bash
spack env activate root_of_repo/env/spack/
spack concretize -f
spack env depsfile -o Makefile
make -j $(nproc)
```

## Note (TO BE DELETED)

Currently some fixes are needed:
```
spack edit py-distributed
spack edit py-dask-expr
```
--> change `py-versioneer@0.28+toml` to `py-versioneer@0.28:+toml`

Pin the spack version to commit: `84276915b9df365bb81b6186087ef1b66eedcc29`

Git clone spack.numpex to obtain updated py-ray expressions:
```
git clone https://github.com/viperML/spack.numpex
cd spack.numpex
git switch ray-update-1.0
```

