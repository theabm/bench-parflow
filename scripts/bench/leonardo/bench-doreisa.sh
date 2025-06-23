#!/bin/bash

#SBATCH --job-name=doreisa
#SBATCH --time=00:12:00
#SBATCH --nodes=2
#SBATCH --exclusive
#SBATCH --partition=dcgp_usr_prod
#SBATCH --qos=normal
#SBATCH --account=EUHPC_D23_125_0

# it is useful to submit a job using something like 
# sbatch -o \"R-%x-%j-$(date +%Y%m%d%H%M%S).o\" -e \"R-%x-%j-$(date +%Y%m%d%H%M%S).e\" myscript.sh
# this will then take the job name (%x) defined here, the job id (%j) defined by slurm, and the date (which wont expand in this file)

# boost partition 2 cpu per node with 32 cores per cpu

start_script=$(date +%s)

mkdir -p ./experiments-doreisa/


if [[ "$#" -lt 1 ]]; then
  echo "Error: An ID for the configuration must be provided."
  exit 1
fi
CONFIG_ID=$1

bash ./scripts/run/leonardo/start_multinode_doreisa.sh 0 $CONFIG_ID

mv R-${SLURM_JOB_NAME}-${SLURM_JOB_ID}* clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_*/
mv clayL_*_${SLURM_JOB_NAME}_${SLURM_JOB_ID}_* experiments-doreisa/

end_script=$(date +%s)

echo [SCRIPT] START: $start_script END: $end_script DIFF: $(expr $end_script - $start_script)

