#!/bin/bash

#SBATCH --time=00:10:00
 
#SBATCH --nodes=5
#SBATCH --exclusive

 
#SBATCH --partition=boost_usr_prod
#SBATCH --qos=normal
#SBATCH --job-name=doreisa-$1
#SBATCH --err=doreisa-5.err
#SBATCH --out=doreisa-5.out
#SBATCH --account=EUHPC_D23_125


bash ./scripts/bench/leonardo/bench-doreisa.sh 0

