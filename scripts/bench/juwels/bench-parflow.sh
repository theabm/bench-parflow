#!/bin/bash

#SBATCH --job-name=parflow
#SBATCH --time=00:12:00
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=30
#SBATCH --cpus-per-task=1
#SBATCH --partition=booster
#SBATCH --account=esmtst

# it is useful to submit a job using something like 
# sbatch -o \"R-%x-%j-$(date +%Y%m%d%H%M%S).o\" -e \"R-%x-%j-$(date +%Y%m%d%H%M%S).e\" myscript.sh
# this will then take the job name (%x) defined here, the job id (%j) defined by slurm, and the date (which wont expand in this file)

# boost partition 2 cpu per node with 32 cores per cpu

start_script=$(date +%s)

mkdir -p ./experiments-parflow/


if [[ "$#" -lt 1 ]]; then
  CONFIG_ID=0
else
  CONFIG_ID=$1
fi

bash ./scripts/run/juwels/start_multinode_parflow.sh 0 $CONFIG_ID

mv R-${SLURM_JOB_NAME}-${SLURM_JOB_ID}* clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_*/
mv clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_* experiments-parflow/

end_script=$(date +%s)

echo [SCRIPT] START: $start_script END: $end_script DIFF: $(expr $end_script - $start_script)

