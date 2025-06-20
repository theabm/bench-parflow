import os
import sys
import time
import multiprocessing as mp
import psutil
import argparse
from concurrent.futures import ProcessPoolExecutor
import threading
from typing import Optional, List

def get_current_cpu():
    """Get the CPU core this process is currently running on"""
    try:
        return psutil.Process().cpu_num()
    except:
        return -1

def get_cpu_affinity():
    """Get the CPU affinity mask for this process"""
    try:
        return psutil.Process().cpu_affinity()
    except:
        return []

def worker_process(worker_id, total_workers):
    """
    Worker process that records its info and does CPU-intensive work
    """
    pid = os.getpid()
    current_cpu = get_current_cpu()
    available_cpus = get_cpu_affinity()
    total_system_cpus = psutil.cpu_count()
    
    # Print initial info
    print(f"Worker {worker_id:2d}: PID={pid:5d}, Current_CPU={current_cpu:2d}, "
          f"Available_CPUs={len(available_cpus):2d} {sorted(available_cpus)}, "
          f"Total_System_CPUs={total_system_cpus}")
    
    # Do CPU-intensive work for 10 seconds to stay active
    start_time = time.time()
    counter = 0
    
    # Busy loop with some actual computation
    migrations = 0
    while time.time() - start_time < 10.0:
        # Some CPU-intensive work
        for i in range(10000):
            counter += i * i % 1000
        
        # Check CPU every second and report if it changes
        if int(time.time() - start_time) % 2 == 0:
            new_cpu = get_current_cpu()
            if new_cpu != current_cpu and new_cpu != -1:
                print(f"Worker {worker_id:2d}: CPU migration {current_cpu} -> {new_cpu}")
                current_cpu = new_cpu
                migrations += 1
    
    # Final report
    final_cpu = get_current_cpu()
    print(f"Worker {worker_id:2d}: FINISHED on CPU {final_cpu}, counter={counter}")
    
    return {
        'worker_id': worker_id,
        'pid': pid,
        'initial_cpu': current_cpu,
        'final_cpu': final_cpu,
        'available_cpus': available_cpus,
        'total_system_cpus': total_system_cpus,
        'counter': counter,
        'migrations': migrations
    }

def set_worker_affinity(worker_id, total_workers, affinity: Optional[List[int]] = None):
    """
    Set CPU affinity for a worker to spread them out
    """
    total_cpus = psutil.cpu_count()

    if affinity is None:
        return

    else:
        cpu_id = affinity[worker_id % len(affinity)]

        try:
            psutil.Process().cpu_affinity([cpu_id])
            print(f"Worker {worker_id}: Set affinity to CPU {cpu_id} (custom)")
        except Exception as e:
            print(f"Worker {worker_id}: Failed to set affinity to CPU {cpu_id}: {e}")

def worker(args):
    """Simple wrapper for worker_process setting"""
    worker_id, total_workers, affinity = args

    set_worker_affinity(worker_id, total_workers, affinity)

    return worker_process(worker_id, total_workers)

def parse_affinity_list(arg):
    """Parse a comma-separated list of ints from the command line"""
    try:
        return [int(x) for x in arg.split(',') if x.strip()]
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid affinity list: {arg}")

def main():
    parser = argparse.ArgumentParser(description='Test CPU affinity and process spreading')
    parser.add_argument('N', type=int, help='Number of processes to spawn')
    parser.add_argument('--show-initial', action='store_true', 
                       help='Show initial CPU affinity of parent process')
    parser.add_argument('--affinity-list', type=parse_affinity_list, default=None, metavar='LIST',
                       help='Comma-separated list of CPU ids to set affinity for worker processes (e.g. 0,1,2,3)')

    args = parser.parse_args()
    
    if args.N <= 0:
        print("Error: N must be positive")
        sys.exit(1)

    if args.affinity_list is not None and len(args.affinity_list) != args.N:
        print("Error: --affinity-list must be a list of CPUs with length equal to N")
        sys.exit(1)

    total_cpus = psutil.cpu_count()
    print(f"=== CPU Affinity Test ===")
    print(f"System CPUs: {total_cpus}")
    print(f"Spawning {args.N} processes")
    
    if args.show_initial:
        parent_affinity = get_cpu_affinity()
        print(f"Parent process affinity: {sorted(parent_affinity)} ({len(parent_affinity)} CPUs)")
    
    print(f"{'='*80}")
    
    # Prepare arguments for workers
    if args.affinity_list:
        print(f"Using custom affinity list: {args.affinity_list}")
        worker_args = [(i, args.N, args.affinity_list) for i in range(args.N)]
        worker_func = worker
    else:
        worker_args = [(i, args.N, None) for i in range(args.N)]
        worker_func = worker

    # Start all workers
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=args.N) as executor:
        results = list(executor.map(worker_func, worker_args))
    
    end_time = time.time()
    
    print(f"{'='*80}")
    print(f"=== SUMMARY ===")
    print(f"Total execution time: {end_time - start_time:.2f} seconds")
    
    # Analyze CPU distribution
    cpu_usage = {}
    total_migrations = 0
    procs_that_migrated = 0
    
    for result in results:
        initial_cpu = result['initial_cpu']
        
        if initial_cpu != -1:
            cpu_usage[initial_cpu] = cpu_usage.get(initial_cpu, 0) + 1
        
        if result['migrations'] > 0:
            procs_that_migrated += 1

        total_migrations += result['migrations']
    
    print(f"CPU usage distribution: {dict(sorted(cpu_usage.items()))}")
    print(f"Processes that migrated CPUs: {procs_that_migrated}/{args.N}")
    print(f"Total CPU migrations: {total_migrations}")
    
    # Check if processes respected affinity constraints
    if args.show_initial:
        parent_affinity = set(get_cpu_affinity())
        violations = 0
        for result in results:
            worker_cpus = set(result['available_cpus'])
            if not worker_cpus.issubset(parent_affinity):
                violations += 1
        
        if violations > 0:
            print(f"⚠️  AFFINITY VIOLATIONS: {violations}/{args.N} processes escaped parent affinity!")
        else:
            print(f"✅ All processes respected parent affinity constraints")

if __name__ == "__main__":
    main()
    
    # Notes:
    # First run: salloc -N 1 --ntasks=1 --cpus-per-task=4 --partition=lrd_all_serial --qos=normal --account=EUHPC_D23_125_0 --time=0:30:00
    # This allocates 4 CPUs on a single node for a single task.

    # Exp 1: See if bash inherits CPU affinity
    # 
    # [abermeom@login05 bench-parflow]$ srun --cpu-bind=core,verbose --ntasks=1 --cpus-per-task=4 bash -c 'echo "Before taskset:"; cat /proc/self/status | grep Cpus_allowed_list'
    # cpu-bind=MASK - login08, task  0  0 [2499314]: mask 0x8000000040000000800000004 set
    # Before taskset:
    # Cpus_allowed_list:      2,35,66,99
    # 
    # We can see there is a match between the CPU mask and the allowed CPUs. If we try to use taskset to use CPUs other than what is allowed, it will fail.
    # 
    # [abermeom@login05 bench-parflow]$ srun --cpu-bind=core,verbose --ntasks=1 --cpus-per-task=4 bash -c 'taskset -c 1,34,65,98 cat /proc/self/status | grep Cpus_allowed_list'
    # cpu-bind=MASK - login08, task  0  0 [2499612]: mask 0x8000000040000000800000004 set
    # taskset: failed to set pid 2499616's affinity: Invalid argument
    # srun: error: login08: task 0: Exited with exit code 1
    #
    # If we specify a subset of allowed CPUs, it will succeed, but only allow the subset. 
    # 
    # [abermeom@login05 bench-parflow]$ srun --cpu-bind=core,verbose --ntasks=1 --cpus-per-task=4 bash -c 'taskset -c 2,35,66,98 cat /proc/self/status | grep Cpus_allowed_list'
    # cpu-bind=MASK - login08, task  0  0 [2499590]: mask 0x8000000040000000800000004 set
    # Cpus_allowed_list:      2,35,66
    # 
    # Conclusion: Bash inherits the CPU affinity from the srun command, and taskset can be used to modify it within the allowed CPUs. 
    # If you try to set an affinity that is not allowed, it will fail with an "Invalid argument" error, if you set an affinity that is a 
    # subset of the allowed CPUs, it will succeed but only allow the specified CPUs.
    #
    # Exp 2: See if Python can spawn processes that can violate CPU affinity
    #
    # First we run a simple test to see if Python can spawn processes that respect the CPU affinity set by srun. 
    # We see that it does respect the CPU affinity, but we can also see that the processes can migrate to other CPUs within 
    # the allowed CPUs, which is expected behavior.
    #
    # [abermeom@login05 bench-parflow]$ srun --cpu-bind=core --ntasks=1 --cpus-per-task=4 bash -c 'python3 test-affinity.py 4  --show-initial'
    # === CPU Affinity Test ===
    # System CPUs: 128
    # Spawning 4 processes
    # Parent process affinity: [0, 32, 64, 96] (4 CPUs)
    # ================================================================================
    # Worker  0: PID=2557878, Current_CPU= 0, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  0: CPU migration 0 -> 32
    # Worker  0: FINISHED on CPU 32, counter=23388820000
    # Worker  1: PID=2557881, Current_CPU=64, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  1: CPU migration 64 -> 0
    # Worker  1: FINISHED on CPU 0, counter=23642645000
    # Worker  2: PID=2557879, Current_CPU=64, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  2: FINISHED on CPU 64, counter=21432060000
    # Worker  3: PID=2557880, Current_CPU=64, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  3: CPU migration 64 -> 96
    # Worker  3: FINISHED on CPU 96, counter=23596495000
    # ================================================================================
    # === SUMMARY ===
    # Total execution time: 10.04 seconds
    # CPU usage distribution: {0: 1, 32: 1, 64: 1, 96: 1}
    # Processes that migrated CPUs: 3/4
    # Total CPU migrations: 3
    # ✅ All processes respected parent affinity constraints
    #
    # Second, we try to set a custom affinity list that is within a range of non allowed CPUs. 
    # We see that the call to set this affinity fails and it ends up using one of the allowed CPUs.
    # 
    # [abermeom@login05 bench-parflow]$ srun --cpu-bind=core --ntasks=1 --cpus-per-task=4 bash -c 'python3 test-affinity.py 4 --affinity 5,6,7,8 --show-initial'
    # === CPU Affinity Test ===
    # System CPUs: 128
    # Spawning 4 processes
    # Parent process affinity: [0, 32, 64, 96] (4 CPUs)
    # ================================================================================
    # Using custom affinity list: [5, 6, 7, 8]
    # Worker 1: Failed to set affinity to CPU 6: [Errno 22] Invalid argument
    # Worker  1: PID=2558156, Current_CPU=64, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  1: FINISHED on CPU 64, counter=23278060000
    # Worker 3: Failed to set affinity to CPU 8: [Errno 22] Invalid argument
    # Worker  3: PID=2558158, Current_CPU=96, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  3: FINISHED on CPU 96, counter=23148840000
    # Worker 2: Failed to set affinity to CPU 7: [Errno 22] Invalid argument
    # Worker  2: PID=2558157, Current_CPU=32, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  2: FINISHED on CPU 32, counter=22396595000
    # Worker 0: Failed to set affinity to CPU 5: [Errno 22] Invalid argument
    # Worker  0: PID=2558155, Current_CPU= 0, Available_CPUs= 4 [0, 32, 64, 96], Total_System_CPUs=128
    # Worker  0: FINISHED on CPU 0, counter=23278060000
    # ================================================================================
    # === SUMMARY ===
    # Total execution time: 10.01 seconds
    # CPU usage distribution: {0: 1, 32: 1, 64: 1, 96: 1}
    # Processes that migrated CPUs: 0/4
    # Total CPU migrations: 0
    # ✅ All processes respected parent affinity constraints
    #
    # Conclusion: Python can spawn processes that respect the CPU affinity set by srun.
    # If you try to set an affinity that is not allowed, it will fail and the process will use one of the allowed CPUs instead.
    #
    # Final conclusion:
    # srun is enough to guarantee that Ray is not using more CPUs than allowed.