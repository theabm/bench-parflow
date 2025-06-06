#!/usr/bin/env python3
"""
Batch Experiment Timing Parser

This script processes multiple experiments in a directory structure and extracts timing
metrics from distributed MPI applications with Ray components. Results are saved to CSV.
"""

import re
import csv
import statistics
import argparse
import glob
from pathlib import Path
from typing import List, Tuple, Dict, Optional, NamedTuple


class ExperimentResult(NamedTuple):
    """Container for experiment results."""
    experiment_name: str
    num_ranks: int
    simulation_total_runtime: Optional[float]
    avg_init_time: Optional[float]
    stddev_init_time: Optional[float]
    avg_publish_time_per_step: Optional[float]
    avg_sum_publish_time_per_rank: Optional[float]
    sum_init_and_avg_publish: Optional[float]
    avg_graph_formation_time: Optional[float]
    avg_graph_compute_time: Optional[float]
    total_analytics_time: Optional[float]


class TimingParser:
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset parser state for a new experiment."""
        self.simulation_runtime = None
        self.init_times = []
        self.publish_times_by_rank = {}
        self.timings_graph = []
        self.timings_compute = []
    
    def parse_csv_file(self, csv_file_path: str) -> None:
        """Parse the *.out.timing.csv file to extract Total Runtime."""
        try:
            with open(csv_file_path, 'r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if row['Timer'] == 'Total Runtime':
                        self.simulation_runtime = float(row['Time (s)'])
                        break
        except FileNotFoundError:
            print(f"    ❌ CSV file not found: {csv_file_path}")
        except Exception as e:
            print(f"    ❌ Error parsing CSV file: {e}")
    
    def parse_log_file(self, log_file_path: str) -> None:
        """Parse the R-.o log file to extract timing information."""
        try:
            with open(log_file_path, 'r') as file:
                content = file.read()
            
            # Extract TIMINGS_GRAPH
            graph_match = re.search(r'TIMINGS GRAPH:\s*\[([\d\., ]+)\]', content)
            if graph_match:
                self.timings_graph = [float(x.strip()) for x in graph_match.group(1).split(',')]
            
            # Extract TIMINGS_COMPUTE
            compute_match = re.search(r'TIMINGS_COMPUTE:\s*\[([\d\., ]+)\]', content)
            if compute_match:
                self.timings_compute = [float(x.strip()) for x in compute_match.group(1).split(',')]
            
            # Extract initialization times
            init_pattern = r'Init rank (\d+) took ([\d\.]+)'
            init_matches = re.findall(init_pattern, content)
            for rank, time_str in init_matches:
                self.init_times.append(float(time_str))
            
            # Extract publish times
            publish_pattern = r'Publish rank (\d+) at step (\d+) took ([\d\.]+)'
            publish_matches = re.findall(publish_pattern, content)
            for rank, step, time_str in publish_matches:
                rank = int(rank)
                step = int(step)
                time_val = float(time_str)
                
                if rank not in self.publish_times_by_rank:
                    self.publish_times_by_rank[rank] = {}
                self.publish_times_by_rank[rank][step] = time_val
            
        except FileNotFoundError:
            print(f"    ❌ Log file not found: {log_file_path}")
        except Exception as e:
            print(f"    ❌ Error parsing log file: {e}")
    
    def get_num_ranks(self) -> int:
        """Calculate the number of ranks from the parsed data."""
        # Count unique ranks from initialization times and publish times
        ranks_from_init = len(self.init_times)
        ranks_from_publish = len(self.publish_times_by_rank)
        
        # Use the maximum of both counts as the number of ranks
        return max(ranks_from_init, ranks_from_publish)
    
    def calculate_metrics(self) -> Dict:
        """Calculate all requested timing metrics."""
        metrics = {}
        
        # Number of ranks
        metrics['num_ranks'] = self.get_num_ranks()
        
        # Simulation runtime (from CSV)
        metrics['simulation_total_runtime'] = self.simulation_runtime
        
        # 1. Average initialization time (with std-dev) across all ranks
        if self.init_times:
            metrics['avg_init_time'] = statistics.mean(self.init_times)
            metrics['stddev_init_time'] = statistics.stdev(self.init_times) if len(self.init_times) > 1 else 0.0
        else:
            metrics['avg_init_time'] = None
            metrics['stddev_init_time'] = None
        
        # Collect all publish times for further calculations
        all_publish_times = []
        publish_sums_by_rank = []
        
        for rank, steps in self.publish_times_by_rank.items():
            rank_publish_times = list(steps.values())
            all_publish_times.extend(rank_publish_times)
            publish_sums_by_rank.append(sum(rank_publish_times))
        
        # 2. Average publish time per step across all ranks
        if all_publish_times:
            metrics['avg_publish_time_per_step'] = statistics.mean(all_publish_times)
        else:
            metrics['avg_publish_time_per_step'] = None
        
        # 3. Average sum of publish time (for all time steps) across all ranks
        if publish_sums_by_rank:
            metrics['avg_sum_publish_time_per_rank'] = statistics.mean(publish_sums_by_rank)
        else:
            metrics['avg_sum_publish_time_per_rank'] = None
        
        # 4. Sum of steps 1 and 3 (avg_init_time + avg_sum_publish_time_per_rank)
        if metrics['avg_init_time'] is not None and metrics['avg_sum_publish_time_per_rank'] is not None:
            metrics['sum_init_and_avg_publish'] = metrics['avg_init_time'] + metrics['avg_sum_publish_time_per_rank']
        else:
            metrics['sum_init_and_avg_publish'] = None
        
        # Analytics timing calculations
        # 1. Average time to form the graph (average across the 9 steps)
        if self.timings_graph:
            metrics['avg_graph_formation_time'] = statistics.mean(self.timings_graph)
        else:
            metrics['avg_graph_formation_time'] = None
        
        # 2. Average time to compute the graph (average across the 9 steps)
        if self.timings_compute:
            metrics['avg_graph_compute_time'] = statistics.mean(self.timings_compute)
        else:
            metrics['avg_graph_compute_time'] = None
        
        # 3. Sum of the two lists: total time of the main analytics
        if self.timings_graph and self.timings_compute:
            metrics['total_analytics_time'] = sum(self.timings_graph) + sum(self.timings_compute)
        else:
            metrics['total_analytics_time'] = None
        
        return metrics


class BatchExperimentProcessor:
    def __init__(self, experiments_dir: str):
        self.experiments_dir = Path(experiments_dir)
        self.parser = TimingParser()
        self.results = []
    
    def find_experiment_directories(self) -> List[Path]:
        """Find all experiment directories."""
        if not self.experiments_dir.exists():
            raise FileNotFoundError(f"Experiments directory not found: {self.experiments_dir}")
        
        experiment_dirs = [d for d in self.experiments_dir.iterdir() if d.is_dir()]
        experiment_dirs.sort()  # Sort for consistent ordering
        return experiment_dirs
    
    def find_files_in_experiment(self, experiment_dir: Path) -> Tuple[Optional[str], Optional[str]]:
        """Find the R-*.o and *out.timing.csv files in an experiment directory."""
        
        # Find R-*.o file
        r_files = list(experiment_dir.glob("R-*.o"))
        r_file = r_files[0] if r_files else None
        
        # Find *out.timing.csv file
        csv_files = list(experiment_dir.glob("*out.timing.csv"))
        csv_file = csv_files[0] if csv_files else None
        
        return (str(r_file) if r_file else None, str(csv_file) if csv_file else None)
    
    def process_experiment(self, experiment_dir: Path) -> Optional[ExperimentResult]:
        """Process a single experiment directory."""
        experiment_name = experiment_dir.name
        print(f"  📁 Processing experiment: {experiment_name}")
        
        # Reset parser for new experiment
        self.parser.reset()
        
        # Find files
        r_file, csv_file = self.find_files_in_experiment(experiment_dir)
        
        if not r_file:
            print(f"    ❌ No R-*.o file found in {experiment_name}")
            return None
        
        if not csv_file:
            print(f"    ❌ No *out.timing.csv file found in {experiment_name}")
            return None
        
        print(f"    📄 Found R file: {Path(r_file).name}")
        print(f"    📄 Found CSV file: {Path(csv_file).name}")
        
        # Parse files
        self.parser.parse_csv_file(csv_file)
        self.parser.parse_log_file(r_file)
        
        # Calculate metrics
        metrics = self.parser.calculate_metrics()
        
        # Create result
        result = ExperimentResult(
            experiment_name=experiment_name,
            num_ranks=metrics['num_ranks'],
            simulation_total_runtime=metrics['simulation_total_runtime'],
            avg_init_time=metrics['avg_init_time'],
            stddev_init_time=metrics['stddev_init_time'],
            avg_publish_time_per_step=metrics['avg_publish_time_per_step'],
            avg_sum_publish_time_per_rank=metrics['avg_sum_publish_time_per_rank'],
            sum_init_and_avg_publish=metrics['sum_init_and_avg_publish'],
            avg_graph_formation_time=metrics['avg_graph_formation_time'],
            avg_graph_compute_time=metrics['avg_graph_compute_time'],
            total_analytics_time=metrics['total_analytics_time']
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
        
        print(f"\n✅ Successfully processed {len(self.results)} out of {len(experiment_dirs)} experiments")
    
    def save_results_to_csv(self, output_file: str) -> None:
        """Save all results to a CSV file."""
        if not self.results:
            print("❌ No results to save")
            return
        
        # Define CSV headers
        headers = [
            'experiment_name',
            'num_ranks',
            'simulation_total_runtime',
            'avg_init_time',
            'stddev_init_time',
            'avg_publish_time_per_step',
            'avg_sum_publish_time_per_rank',
            'sum_init_and_avg_publish',
            'avg_graph_formation_time',
            'avg_graph_compute_time',
            'total_analytics_time'
        ]
        
        try:
            with open(output_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(headers)
                
                # Write data rows
                for result in self.results:
                    writer.writerow([
                        result.experiment_name,
                        result.num_ranks,
                        result.simulation_total_runtime,
                        result.avg_init_time,
                        result.stddev_init_time,
                        result.avg_publish_time_per_step,
                        result.avg_sum_publish_time_per_rank,
                        result.sum_init_and_avg_publish,
                        result.avg_graph_formation_time,
                        result.avg_graph_compute_time,
                        result.total_analytics_time
                    ])
            
            print(f"💾 Results saved to: {output_file}")
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    
    def print_summary(self) -> None:
        """Print a summary of all processed experiments."""
        if not self.results:
            return
        
        print("\n" + "="*80)
        print("BATCH EXPERIMENT TIMING ANALYSIS SUMMARY")
        print("="*80)
        
        for result in self.results:
            print(f"\n📊 {result.experiment_name} ({result.num_ranks} ranks):")
            print(f"    Simulation Runtime: {result.simulation_total_runtime:.6f}s" if result.simulation_total_runtime else "    Simulation Runtime: N/A")
            print(f"    Avg Init Time: {result.avg_init_time:.6f}s ± {result.stddev_init_time:.6f}s" if result.avg_init_time else "    Avg Init Time: N/A")
            print(f"    Total Analytics Time: {result.total_analytics_time:.6f}s" if result.total_analytics_time else "    Total Analytics Time: N/A")


def main():
    """Main function to run the batch experiment analysis."""
    parser = argparse.ArgumentParser(
        description="Process multiple distributed application timing experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python timing_parser.py experiments/
  python timing_parser.py experiments/ --output results.csv
  python timing_parser.py /path/to/experiments --output /path/to/output.csv --verbose
        """
    )
    
    parser.add_argument(
        'experiments_dir',
        help='Directory containing experiment subdirectories'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='experiment_timing_results.csv',
        help='Output CSV file path (default: experiment_timing_results.csv)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed summary of results'
    )
    
    args = parser.parse_args()
    
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
