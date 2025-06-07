#!/bin/bash

#SBATCH --job-name=parflow
#SBATCH --time=00:12:00
#SBATCH --nodes=4
#SBATCH --exclusive
#SBATCH --partition=boost_usr_prod
#SBATCH --qos=normal
#SBATCH --account=EUHPC_D23_125

# it is useful to submit a job using something like 
# sbatch -o \"R-%x-%j-$(date +%Y%m%d%H%M%S).o\" -e \"R-%x-%j-$(date +%Y%m%d%H%M%S).e\" myscript.sh
# this will then take the job name (%x) defined here, the job id (%j) defined by slurm, and the date (which wont expand in this file)

# boost partition 2 cpu per node with 32 cores per cpu

mkdir -p ./experiments-parflow/

bash ./scripts/run/leonardo/start_multinode_parflow.sh

mv R-${SLURM_JOB_NAME}-${SLURM_JOB_ID}* clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_*/
mv clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_* experiments-parflow/
