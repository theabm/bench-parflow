"""
Batch Experiment Timing Parser

This script processes multiple experiments in a directory structure and extracts timing
metrics from distributed MPI applications with Ray components. Results are saved to CSV.
Supports both regular experiments and DEISA experiments with different output formats.
"""

# TODO : ADD EXP ID
# TODO : ADD ABSOLUTE TIMING?

import re
import csv
import statistics
import argparse
import glob
from pathlib import Path
from typing import List, Tuple, Dict, Optional, NamedTuple


class ExperimentResult(NamedTuple):
    """Container for experiment results."""

    # name of the experiment
    experiment_name: str
    # experiment id -- used to group and average
    experiment_id: int
    # number of MPI ranks
    num_ranks: int
    # number of steps of the simulation
    num_steps: int
    # total run time, as reported by parflow
    simulation_total_runtime: Optional[float]
    # richards exclude 1st step, as reported by parflow
    richards_exclude_first_step: Optional[float]
    # average initialization time of client (using PDI)
    avg_init_time: Optional[float]
    # variance of initialization time
    stdev_init_time: Optional[float]
    # per time step average time needed to send/add chunk aka publish it
    step_publish_times: Dict[int, Optional[float]]
    # stdev per time step
    stdev_step_publish_times: Dict[int, Optional[float]]
    # average time to publish the data (across all ranks and all steps)
    avg_publish_time: Optional[float]
    # average time spend in PDI per rank (computed as average init + average publish time * numsteps)
    avg_pdi_time_per_rank: Optional[float]
    # avg time to form graph - ONLY DOREISA (DEISA ONLY DOES IT ONCE)
    avg_graph_formation_time: Optional[float]
    stdev_graph_formation_time: Optional[float]
    # avg time to compute the graph
    avg_graph_compute_time: Optional[float]
    stdev_graph_compute_time: Optional[float]
    # total time of analytics
    total_analytics_time: Optional[float]


class TimingParser:
    def __init__(self, is_deisa: bool = False):
        self.is_deisa = is_deisa
        self.reset()

    def reset(self):
        """Reset parser state for a new experiment."""
        self.simulation_runtime = None
        self.richards_exclude_first_step = None
        self.experiment_id = None

        self.num_steps = 0

        self.init_time_start = []
        self.init_time_end = []
        self.init_times = []

        self.publish_times_by_rank = {}

        self.timings_graph_start = []
        self.timings_graph_end = []
        self.timings_graph = []

        self.timings_compute_start = []
        self.timings_compute_end = []
        self.timings_compute = []

    def parse_csv_file(self, csv_file_path: str) -> None:
        """Parse the *.out.timing.csv file to extract Total Runtime."""
        try:
            with open(csv_file_path, "r") as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if row["Timer"] == "Richards Exclude 1st Time Step":
                        self.richards_exclude_first_step = float(row["Time (s)"])
                    if row["Timer"] == "Total Runtime":
                        self.simulation_runtime = float(row["Time (s)"])
                        break
        except FileNotFoundError:
            print(f"    ❌ CSV file not found: {csv_file_path}")
        except Exception as e:
            print(f"    ❌ Error parsing CSV file: {e}")

    def parse_log_file(self, log_file_path: str) -> None:
        """Parse the *.out.log file to extract Total Runtime."""
        try:
            with open(log_file_path, "r") as file:
                content = file.read()

            steps_match = re.search(r"Total Timesteps\s*:\s*(\d+)", content)

            if steps_match:
                steps = steps_match.group(1)
                self.num_steps = int(steps) + 1

        except FileNotFoundError:
            print(f"    ❌ Log file not found: {log_file_path}")
        except Exception as e:
            print(f"    ❌ Error parsing log file: {e}")

    def parse_output_file(self, log_file_path: str) -> None:
        """Parse the R-.o log file to extract timing information."""
        try:
            with open(log_file_path, "r") as file:
                content = file.read()

            self._parse_regular_format(content)

        except FileNotFoundError:
            print(f"    ❌ Log file not found: {log_file_path}")
        except Exception as e:
            print(f"    ❌ Error parsing log file: {e}")

    def _parse_regular_format(self, content: str) -> None:
        """Parse"""
        # extract experiment_id
        exp_id_match = re.search(r"CONFIG_ID\s*:\s*(\d+)", content)

        if exp_id_match:
            exp_id = exp_id_match.group(1)
            self.experiment_id = int(exp_id)

        # Extract TIMINGS GRAPH - match the entire list after the colon
        graph_match = re.search(r"TIMINGS GRAPH:\s*(\[.*?\])", content)
        if graph_match:
            try:
                timings_graph = eval(
                    graph_match.group(1)
                )  # Convert string representation to actual list of tuples
                self.timings_graph_start = [elem[0] for elem in timings_graph]
                self.timings_graph_end = [elem[1] for elem in timings_graph]
                self.timings_graph = [elem[2] for elem in timings_graph]

            except:
                print("No match of TIMINGS GRAPH")
                self.timings_graph_start = []
                self.timings_graph_end = []
                self.timings_graph = []

        # Extract TIMINGS COMPUTE - match the entire list after the colon
        compute_match = re.search(r"TIMINGS COMPUTE:\s*(\[.*?\])", content)
        if compute_match:
            try:
                timings_compute = eval(
                    compute_match.group(1)
                )  # Convert string representation to actual list of tuples
                self.timings_compute_start = [elem[0] for elem in timings_compute]
                self.timings_compute_end = [elem[1] for elem in timings_compute]
                self.timings_compute = [elem[2] for elem in timings_compute]
            except:
                print("No match of TIMINGS COMPUTE")
                self.timings_compute_start = []
                self.timings_compute_end = []
                self.timings_compute = []

        # Extract initialization times
        init_pattern = r"\[PDI, SETUP, (\d+)\] START: (\d+(?:\.\d+)?) END: (\d+(?:\.\d+)?) DIFF: (\d+(?:\.\d+)?)"
        init_matches = re.findall(init_pattern, content)
        for rank, start, end, diff in init_matches:
            self.init_times.append(float(diff))
            self.init_time_start.append(float(start))
            self.init_time_end.append(float(end))

        # Extract publish times
        available_pattern = r"\[PDI, AVAILABLE, (\d+)\] START: (\d+(?:\.\d+)?) END: (\d+(?:\.\d+)?) DIFF: (\d+(?:\.\d+)?) ITER: (\d+) QUANT: (\w+)"
        available_matches = re.findall(available_pattern, content)
        for rank, start, end, diff, step, quant in available_matches:
            # Convert numeric values to appropriate types
            rank = int(rank)
            start = float(start)
            end = float(end)
            time_val = float(diff)
            step = int(step)
            # to be used when using more than one quantity
            quant = str(quant)

            if rank not in self.publish_times_by_rank:
                self.publish_times_by_rank[rank] = {}

            # TODO use start and end
            # record publish time for each rank per timestep
            self.publish_times_by_rank[rank][step] = time_val

    def get_num_ranks(self) -> int:
        """Calculate the number of ranks from the parsed data."""
        # Count unique ranks from initialization times and publish times
        ranks_from_init = len(self.init_times)
        ranks_from_publish = len(self.publish_times_by_rank)

        # Use the maximum of both counts as the number of ranks
        assert ranks_from_publish == ranks_from_init, "Ranks do not match! Error during experiment."

        return ranks_from_init

    def calculate_metrics(self) -> Dict:
        """Calculate all requested timing metrics."""
        metrics = {}

        # Number of ranks
        metrics["num_ranks"] = self.get_num_ranks()
        metrics["experiment_id"] = self.experiment_id

        # Simulation runtime (from CSV)
        metrics["simulation_total_runtime"] = self.simulation_runtime
        metrics["richards_exclude_first_step"] = self.richards_exclude_first_step

        # 1. Average initialization time (with std-dev) across all ranks
        if self.init_times:
            metrics["avg_init_time"] = statistics.mean(self.init_times)
            # metrics["var_init_time"] = (
            #     statistics.variance(self.init_times) if len(self.init_times) > 1 else 0.0
            # )
            metrics["stdev_init_time"] = (
                statistics.stdev(self.init_times) if len(self.init_times) > 1 else 0.0
            )
        else:
            metrics["avg_init_time"] = None
            # metrics["var_init_time"] = None
            metrics["stdev_init_time"] = None

        # Organize publish times by step
        publish_times_by_step = {}
        all_publish_times = []

        for rank, steps in self.publish_times_by_rank.items():
            for step, time_val in steps.items():
                if step not in publish_times_by_step:
                    publish_times_by_step[step] = []
                publish_times_by_step[step].append(time_val)
                all_publish_times.append(time_val)

        # 2. Average publish time for each step (NEW: per-step averages)
        for step in sorted(publish_times_by_step.keys()):
            step_times = publish_times_by_step[step]
            if step_times:
                metrics[f"avg_publish_time_step_{step}"] = statistics.mean(step_times)
                metrics[f"stdev_publish_time_step_{step}"] = statistics.stdev(step_times)
            else:
                metrics[f"avg_publish_time_step_{step}"] = None
                metrics[f"stdev_publish_time_step_{step}"] = None

        # Store the number of steps for later use
        metrics["num_steps"] = len(publish_times_by_step) if publish_times_by_step else 0

        if publish_times_by_step:
            # we are in parflow case
            metrics["num_steps"] = len(publish_times_by_step)

            assert metrics["num_steps"] == self.num_steps

        else:
            metrics["num_steps"] = self.num_steps

        # 3. Average sum of publish time (CORRECTED: sum of all publish times / (nranks * nsteps))
        if all_publish_times and metrics["num_ranks"] > 0 and metrics["num_steps"] > 0:
            total_publish_time = sum(all_publish_times)
            total_expected_entries = metrics["num_ranks"] * metrics["num_steps"]
            metrics["avg_publish_time_one_step"] = total_publish_time / total_expected_entries
            # TODO stdev?  HOW TO CATCH OUTLIERS? BOX PLOT with max and min?
        else:
            metrics["avg_publish_time_one_step"] = None

        # 4. Sum of steps 1 and 3 (avg_init_time + avg_publish_time
        if (
            metrics["avg_init_time"] is not None
            and metrics["avg_publish_time_one_step"] is not None
            and metrics["num_steps"] is not None
        ):
            metrics["avg_time_pdi"] = (
                metrics["avg_init_time"]
                + metrics["avg_publish_time_one_step"] * metrics["num_steps"]
            )
        else:
            metrics["avg_time_pdi"] = None

        # Analytics timing calculations
        if self.is_deisa:
            # For DEISA: values are already averaged/final
            # 1. Graph formation time (already averaged)
            if self.timings_graph:
                metrics["avg_graph_formation_time"] = self.timings_graph[0]
                metrics["stdev_graph_formation_time"] = 0
            else:
                metrics["avg_graph_formation_time"] = None
                metrics["stdev_graph_formation_time"] = None

            # 2. Graph compute time (already final)
            if self.timings_compute:
                metrics["avg_graph_compute_time"] = self.timings_compute[0]
                metrics["stdev_graph_compute_time"] = 0
            else:
                metrics["avg_graph_compute_time"] = None
                metrics["stdev_graph_compute_time"] = None

            # 3. Total analytics time
            if self.timings_graph and self.timings_compute:
                metrics["total_analytics_time"] = self.timings_graph[0] + self.timings_compute[0]
            else:
                metrics["total_analytics_time"] = None
        else:
            # For regular experiments: calculate averages and sums
            # 1. Average time to form the graph (average across the 9 steps)
            if self.timings_graph:
                # TODO stdev or max min?
                metrics["avg_graph_formation_time"] = statistics.mean(self.timings_graph)
                metrics["stdev_graph_formation_time"] = statistics.stdev(self.timings_graph)
            else:
                metrics["avg_graph_formation_time"] = None
                metrics["stdev_graph_formation_time"] = None

            # 2. Average time to compute the graph (average across the 9 steps)
            if self.timings_compute:
                metrics["avg_graph_compute_time"] = statistics.mean(self.timings_compute)
                metrics["stdev_graph_compute_time"] = statistics.stdev(self.timings_compute)
            else:
                metrics["avg_graph_compute_time"] = None
                metrics["stdev_graph_compute_time"] = None

            # 3. Sum of the two lists: total time of the main analytics
            if self.timings_graph and self.timings_compute:
                metrics["total_analytics_time"] = sum(self.timings_graph) + sum(
                    self.timings_compute
                )
            else:
                metrics["total_analytics_time"] = None

        return metrics


class BatchExperimentProcessor:
    def __init__(self, experiments_dir: str):
        self.experiments_dir = Path(experiments_dir)
        self.results = []
        # Detect if this is a DEISA experiment directory
        self.is_deisa = "deisa" in str(self.experiments_dir).lower()
        if self.is_deisa:
            print("🧬 Detected DEISA experiment format")

    def find_experiment_directories(self) -> List[Path]:
        """Find all experiment directories."""
        if not self.experiments_dir.exists():
            raise FileNotFoundError(f"Experiments directory not found: {self.experiments_dir}")

        experiment_dirs = [d for d in self.experiments_dir.iterdir() if d.is_dir()]
        experiment_dirs.sort()  # Sort for consistent ordering
        return experiment_dirs

    def find_files_in_experiment(
        self, experiment_dir: Path
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Find the R-*.o, *.out.timing.csv, and *.out.log files in an experiment directory."""

        # Find R-*.o file
        r_files = list(experiment_dir.glob("R-*.o"))
        r_file = r_files[0] if r_files else None

        # Find *.out.timing.csv file
        csv_files = list(experiment_dir.glob("*.out.timing.csv"))
        csv_file = csv_files[0] if csv_files else None

        # Find .out.log file
        log_files = list(experiment_dir.glob("*.out.log"))
        log_file = log_files[0] if log_files else None

        return (
            str(r_file) if r_file else None,
            str(csv_file) if csv_file else None,
            str(log_file) if log_file else None,
        )

    def process_experiment(self, experiment_dir: Path) -> Optional[ExperimentResult]:
        """Process a single experiment directory."""
        experiment_name = experiment_dir.name
        experiment_id = int(str(experiment_name).split("_")[-1])

        print(f"  📁 Processing experiment: {experiment_name}")

        # Create parser with appropriate format detection
        parser = TimingParser(is_deisa=self.is_deisa)

        # Find files
        r_file, csv_file, log_file = self.find_files_in_experiment(experiment_dir)

        if not r_file:
            print(f"    ❌ No R-*.o file found in {experiment_name}")
            return None

        if not csv_file:
            print(f"    ❌ No *.out.timing.csv file found in {experiment_name}")
            return None

        if not log_file:
            print(f"    ❌ No *.out.log file found in {experiment_name}")
            return None

        print(f"    📄 Found R file: {Path(r_file).name}")
        print(f"    📄 Found CSV file: {Path(csv_file).name}")
        print(f"    📄 Found Log file: {Path(log_file).name}")

        # Parse files
        parser.parse_csv_file(csv_file)
        parser.parse_output_file(r_file)
        parser.parse_log_file(log_file)

        # Calculate metrics
        metrics = parser.calculate_metrics()

        if "parflow" in experiment_name:
            parts = experiment_name.split("_")
            if len(parts) >= 3:
                try:
                    metrics["num_ranks"] = int(parts[1]) * int(parts[2]) * int(parts[3])
                except (ValueError, IndexError):
                    pass

        # assert that exp id match
        assert experiment_id == metrics["experiment_id"], "Experiment IDs dont match"

        # Extract step-wise publish times
        step_publish_times = {}
        for key, value in metrics.items():
            if key.startswith("avg_publish_time_step_"):
                step_num = int(key.split("_")[-1])
                step_publish_times[step_num] = value

        stdev_step_publish_times = {}
        for key, value in metrics.items():
            if key.startswith("stdev_publish_time_step_"):
                step_num = int(key.split("_")[-1])
                stdev_step_publish_times[step_num] = value

        # Create result
        result = ExperimentResult(
            experiment_name=experiment_name,
            experiment_id=experiment_id,
            num_ranks=metrics["num_ranks"],
            num_steps=metrics["num_steps"],
            simulation_total_runtime=metrics["simulation_total_runtime"],
            richards_exclude_first_step=metrics["richards_exclude_first_step"],
            avg_init_time=metrics["avg_init_time"],
            stdev_init_time=metrics["stdev_init_time"],
            step_publish_times=step_publish_times,
            stdev_step_publish_times=stdev_step_publish_times,
            avg_publish_time=metrics["avg_publish_time_one_step"],
            avg_pdi_time_per_rank=metrics["avg_time_pdi"],
            avg_graph_formation_time=metrics["avg_graph_formation_time"],
            stdev_graph_formation_time=metrics["stdev_graph_formation_time"],
            avg_graph_compute_time=metrics["avg_graph_compute_time"],
            stdev_graph_compute_time=metrics["stdev_graph_compute_time"],
            total_analytics_time=metrics["total_analytics_time"],
        )

        print(f"    ✅ Processed {metrics['num_ranks']} ranks successfully")
        return result

    def process_all_experiments(self) -> None:
        """Process all experiments in the directory."""
        experiment_dirs = self.find_experiment_directories()

        if not experiment_dirs:
            print(f"❌ No experiment directories found in {self.experiments_dir}")
            return

        print(f"🔍 Found {len(experiment_dirs)} experiment directories")

        for experiment_dir in experiment_dirs:
            result = self.process_experiment(experiment_dir)
            if result:
                self.results.append(result)

        print(
            f"\n✅ Successfully processed {len(self.results)} out of {len(experiment_dirs)} experiments"
        )

    def save_results_to_csv(self, output_file: str) -> None:
        """Save all results to a CSV file."""
        if not self.results:
            print("❌ No results to save")
            return

        # Determine the maximum number of steps across all experiments
        max_steps = max(result.num_steps for result in self.results) if self.results else 0

        # Define CSV headers
        headers = [
            "experiment_name",
            "experiment_id",
            "num_ranks",
            "num_steps",
            "simulation_total_runtime",
            "richards_exclude_first_step",
            "avg_pdi_init_time",
            "stdev_pdi_init_time",
        ]

        # Add step-wise publish time headers
        for step in range(max_steps):
            headers.append(f"avg_publish_time_step_{step}")
            headers.append(f"stdev_publish_time_step_{step}")

        # Add remaining headers
        headers.extend(
            [
                "avg_pdi_publish_time_one_step",
                "avg_time_pdi",
                "avg_graph_formation_time",
                "stdev_graph_formation_time",
                "avg_graph_compute_time",
                "stdev_graph_compute_time",
                "total_analytics_time",
            ]
        )

        try:
            with open(output_file, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(headers)

                # Write data rows
                for result in self.results:
                    row = [
                        result.experiment_name,
                        result.experiment_id,
                        result.num_ranks,
                        result.num_steps,
                        result.simulation_total_runtime,
                        result.richards_exclude_first_step,
                        result.avg_init_time,
                        result.stdev_init_time,
                    ]

                    # Add step-wise publish times
                    for step in range(max_steps):
                        row.append(result.step_publish_times.get(step, None))
                        row.append(result.stdev_step_publish_times.get(step, None))

                    # Add remaining metrics
                    row.extend(
                        [
                            result.avg_publish_time,
                            result.avg_pdi_time_per_rank,
                            result.avg_graph_formation_time,
                            result.stdev_graph_formation_time,
                            result.avg_graph_compute_time,
                            result.stdev_graph_compute_time,
                            result.total_analytics_time,
                        ]
                    )

                    writer.writerow(row)

            print(f"💾 Results saved to: {output_file}")
            print(
                f"📊 CSV contains {len(headers)} columns including {max_steps} step-wise publish time columns"
            )

        except Exception as e:
            print(f"❌ Error saving results: {e}")

    def print_summary(self) -> None:
        """Print a summary of all processed experiments."""
        if not self.results:
            return

        print("\n" + "=" * 80)
        print("BATCH EXPERIMENT TIMING ANALYSIS SUMMARY")
        print("=" * 80)

        for result in self.results:
            print(f"\n📊 {result.experiment_name} ({result.num_ranks} ranks):")
            print(
                f"    Simulation Runtime: {result.simulation_total_runtime:.6f}s"
                if result.simulation_total_runtime
                else "    Simulation Runtime: N/A"
            )
            print(
                f"    Avg Init Time: {result.avg_init_time:.6f}s ± {result.stdev_init_time:.6f}s"
                if result.avg_init_time
                else "    Avg Init Time: N/A"
            )
            print(
                f"    Total Analytics Time: {result.total_analytics_time:.6f}s"
                if result.total_analytics_time
                else "    Total Analytics Time: N/A"
            )


def main():
    """Main function to run the batch experiment analysis."""
    parser = argparse.ArgumentParser(
        description="Process multiple distributed application timing experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python timing_parser.py experiments/
  python timing_parser.py experiments-deisa/
  python timing_parser.py experiments/ --output results.csv
  python timing_parser.py /path/to/experiments --output /path/to/output.csv --verbose
        """,
    )

    parser.add_argument("experiments_dir", help="Directory containing experiment subdirectories")

    parser.add_argument(
        "--output",
        "-o",
        default="experiment-timings.csv",
        help="Output CSV file path (default: experiment-timings.csv)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print detailed summary of results"
    )

    args = parser.parse_args()
    args.output = args.experiments_dir + args.output

    print("🚀 Starting batch experiment timing analysis...")
    print(f"📂 Experiments directory: {args.experiments_dir}")
    print(f"💾 Output file: {args.output}")

    try:
        # Create processor and run analysis
        processor = BatchExperimentProcessor(args.experiments_dir)
        processor.process_all_experiments()

        # Save results
        processor.save_results_to_csv(args.output)

        # Print summary if requested
        if args.verbose:
            processor.print_summary()

        print("\n🎉 Analysis completed successfully!")

    except FileNotFoundError as e:
        print(f"❌ {e}")
    except KeyboardInterrupt:
        print("\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
