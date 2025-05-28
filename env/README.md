# Setting Up The Environment 

There main supported way to set up the environment is SPACK. 

The main testbed is G5K.

## Spack

To use spack, first clone the spack repo and then activate spack.
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
