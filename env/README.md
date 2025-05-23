# Setting Up The Environment 

Load Spack module then activate the environment with root_of_repo/spack.yaml 
```bash
module load spack

spacktivate root_of_repo
```

```bash
guix shell --pure -m root_of_repo/env/guix/manifest-pip.scm

# if building is not cached then run activate.sh. This removes the previous 
#`.venv` and creates another one based on `requirements.txt`. The .venv is created in the 
# root of the project
source root_of_repo/env/python/activate.sh

# OR

# if .venv already exists you can just activate it 
# (make sure you recreate the venv whenever guix downloads dependencies again since the hash of packages might change)
source root_of_repo/.venv/bin/activate
```
