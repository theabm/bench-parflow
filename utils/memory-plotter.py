import pandas as pd
import glob
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import os
import plotly.express as px
import itertools
import re
from collections import defaultdict

# Line styles and thicknesses
LINE_DASHES = ["solid", "dot", "dash", "longdash", "dashdot", "longdashdot"]
LINE_WIDTHS = [2, 1.5, 1]

def generate_host_styles(hostnames):
    colors = px.colors.qualitative.Plotly
    style_map = {}
    total_colors = len(colors)
    total_dashes = len(LINE_DASHES)
    total_widths = len(LINE_WIDTHS)
    for i, full_host in enumerate(sorted(hostnames)):
        short_host = full_host.split(".")[0]  # strip domain
        color_index = i % total_colors
        dash_index = (i // total_colors) % total_dashes
        width_index = (i // (total_colors * total_dashes)) % total_widths
        style_map[full_host] = {
            "shortname": short_host,
            "color": colors[color_index],
            "dash": LINE_DASHES[dash_index],
            "width": LINE_WIDTHS[width_index]
        }
    return style_map

def parse_config_from_dirname(dirname):
    """Extract configuration from directory name like clayL_*_*_*_*"""
    # Assuming the pattern is clayL_ranksx_ranksy_numnodes_*
    # Adjust this regex based on your actual naming convention
    match = re.match(r'clayL_(\d+)_(\d+)_(\d+)_.*', dirname)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        # Fallback: try to extract first 3 numbers from the directory name
        numbers = re.findall(r'\d+', dirname)
        if len(numbers) >= 3:
            return (int(numbers[0]), int(numbers[1]), int(numbers[2]))
    return None

def load_experiment_data(exp_dir):
    """Load all memlog_*.csv files from a single experiment directory"""
    pattern = os.path.join(exp_dir, "memlog_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        print(f"[!] No memlog_*.csv files found in directory: {exp_dir}")
        return None
    
    dfs = [pd.read_csv(file) for file in csv_files]
    df = pd.concat(dfs, ignore_index=True)
    
    # Process the data
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    for col in ["used_bytes", "available_bytes", "free_bytes", "total_bytes"]:
        df[col.replace("_bytes", "_GB")] = df[col] / 1e9
    df.sort_values("timestamp", inplace=True)
    
    # Create relative timestamp in seconds from the start of the experiment
    start_time = df["timestamp"].min()
    df["relative_timestamp"] = (df["timestamp"] - start_time).dt.total_seconds()
    
    return df

def aggregate_experiments(exp_dfs):
    """Aggregate multiple experiment dataframes by taking the mean"""
    if len(exp_dfs) == 1:
        return exp_dfs[0]
    
    # Combine all dataframes
    combined_df = pd.concat(exp_dfs, ignore_index=True)
    
    # Group by relative timestamp and hostname, then take mean of metrics
    metrics = ["used_GB", "available_GB", "free_GB", "total_GB"]
    
    # Round relative timestamps to nearest second to help with grouping
    combined_df["relative_timestamp_rounded"] = combined_df["relative_timestamp"].round(0)
    
    # Group and aggregate
    agg_dict = {metric: "mean" for metric in metrics}
    agg_dict["relative_timestamp"] = "first"  # Keep original relative timestamp
    
    aggregated = combined_df.groupby(["relative_timestamp_rounded", "hostname"]).agg(agg_dict).reset_index()
    aggregated = aggregated.drop("relative_timestamp_rounded", axis=1)
    aggregated.sort_values("relative_timestamp", inplace=True)
    
    return aggregated

def create_memory_plot(df, config):
    """Create the memory usage plot for a given configuration"""
    hostnames = df["hostname"].unique()
    style_map = generate_host_styles(hostnames)
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["Used Memory (GB)", "Available Memory (GB)",
                        "Free Memory (GB)", "Total Memory (GB)"],
        shared_xaxes=True,
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )
    
    plots = [
        ("used_GB", 1, 1),
        ("available_GB", 1, 2),
        ("free_GB", 2, 1),
        ("total_GB", 2, 2),
    ]
    
    for metric, row, col in plots:
        # Sort by shortname
        sorted_hosts = sorted(hostnames, key=lambda h: style_map[h]["shortname"])
        for i, host in enumerate(sorted_hosts):
            host_data = df[df["hostname"] == host]
            show_legend = (row == 1 and col == 1)  # show legend only in top-left
            shortname = style_map[host]["shortname"]
            fig.add_trace(
                go.Scatter(
                    x=host_data["relative_timestamp"],
                    y=host_data[metric],
                    mode="lines",
                    name=shortname if show_legend else None,
                    line=dict(
                        color=style_map[host]["color"],
                        dash=style_map[host]["dash"],
                        width=style_map[host]["width"]
                    ),
                    hovertemplate=f"{shortname}<br>Time: %{{x:.0f}}s<br>{metric}: %{{y:.2f}} GB<extra></extra>",
                    showlegend=show_legend
                ),
                row=row, col=col
            )
    
    ranksx, ranksy, numnodes = config
    fig.update_layout(
        title_text=f"Cluster Memory Usage Over Time (Config: {ranksx}x{ranksy}, {numnodes} nodes)",
        height=900,
        width=1400,
        legend_title="Hostnames",
        hovermode="x unified",
        template="plotly_white",
        xaxis_title="Time (seconds from start)",
        xaxis2_title="Time (seconds from start)",
        xaxis3_title="Time (seconds from start)",
        xaxis4_title="Time (seconds from start)"
    )
    
    return fig

def main():
    parser = argparse.ArgumentParser(description="Generate memory usage reports from experiment directories.")
    parser.add_argument("parent_dir", nargs="?", default=".", 
                       help="Parent directory containing experiment subdirectories (default: current directory)")
    args = parser.parse_args()
    
    parent_dir = args.parent_dir
    
    # Find all experiment directories
    exp_dirs = [d for d in os.listdir(parent_dir) 
                if os.path.isdir(os.path.join(parent_dir, d)) and d.startswith('clayL_')]
    
    if not exp_dirs:
        print(f"[!] No experiment directories found in: {parent_dir}")
        return
    
    # Group experiments by configuration
    config_groups = defaultdict(list)
    
    for exp_dir in exp_dirs:
        config = parse_config_from_dirname(exp_dir)
        if config:
            full_path = os.path.join(parent_dir, exp_dir)
            config_groups[config].append(full_path)
            print(f"[+] Found experiment: {exp_dir} -> config {config}")
        else:
            print(f"[!] Could not parse configuration from directory name: {exp_dir}")
    
    # Create results directory
    results_dir = "./results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Process each configuration
    for config, exp_paths in config_groups.items():
        ranksx, ranksy, numnodes = config
        print(f"\n[+] Processing configuration: {ranksx}x{ranksy}, {numnodes} nodes ({len(exp_paths)} experiments)")
        
        # Load data from all experiments for this configuration
        exp_dfs = []
        for exp_path in exp_paths:
            df = load_experiment_data(exp_path)
            if df is not None:
                exp_dfs.append(df)
                print(f"    Loaded data from: {os.path.basename(exp_path)}")
        
        if not exp_dfs:
            print(f"[!] No valid data found for configuration {config}")
            continue
        
        # Aggregate the experiments (take mean)
        aggregated_df = aggregate_experiments(exp_dfs)
        print(f"    Aggregated {len(exp_dfs)} experiments")
        
        # Create the plot
        fig = create_memory_plot(aggregated_df, config)
        
        # Save the plot with parent directory name included
        parent_name = os.path.basename(os.path.abspath(parent_dir))
        output_file = os.path.join(results_dir, f"memory_report_{ranksx}_{ranksy}_{numnodes}_{parent_name}.html")
        fig.write_html(output_file)
        print(f"[✓] Memory report saved to: {output_file}")

if __name__ == "__main__":
    main()
