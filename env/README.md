# Setting Up The Environment 

## Guix
The basic requirement is to have guix installed. The testbed for all these scripts is G5K.

Before running the scripts, run this command which will be useful for later:

```bash
bash root_of_repo/guix/guix-package.sh
```
This creates a `profile` and `profile-1-link` which we can use later in the scripts to setup the environment on many nodes.

To build the repository, you need to setup the environment using the following commands:
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
