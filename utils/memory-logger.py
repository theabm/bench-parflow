import psutil
import time
import socket
import os
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Log memory usage periodically.")
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in seconds between memory samples (default: 5)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    hostname = socket.gethostname()
    job_id = os.environ.get("SLURM_JOB_ID", "nojob")
    log_file = f"./memlog_{job_id}_{hostname}.csv"

    print(f"[memory_logger] Logging to {log_file} every {args.interval}s")

    with open(log_file, "a") as f:
        f.write(
            "timestamp,hostname,job_id,used_bytes,available_bytes,free_bytes,total_bytes\n"
        )  # CSV header
        while True:
            mem = psutil.virtual_memory()
            timestamp = time.time()
            f.write(
                f"{timestamp},{hostname},{job_id},{mem.used},{mem.available},{mem.free},{mem.total}\n"
            )
            f.flush()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
