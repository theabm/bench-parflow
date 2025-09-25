import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re


def process_parflow_data(df):
    """Process parflow data with proper aggregation and statistics"""
    # Group by experiment_id and calculate appropriate statistics
    grouped = (
        df.groupby("experiment_id")
        .agg(
            {
                "num_ranks": "first",  # Take first value since it's constant per experiment
                "num_steps": "first",
                "simulation_total_runtime": ["mean", "std"],
                "richards_exclude_first_step": ["mean", "std"],
            }
        )
        .reset_index()
    )

    # Flatten column names
    grouped.columns = [
        "experiment_id",
        "num_ranks",
        "num_steps",
        "simulation_total_runtime_mean",
        "simulation_total_runtime_stdev",
        "richards_exclude_first_step_mean",
        "richards_exclude_first_step_stdev",
    ]

    return grouped


def process_doreisa_data(df):
    """Process doreisa data"""
    # Identify columns to exclude from mean/std calculation
    excluded_cols = ["experiment_id", "experiment_name", "num_ranks", "num_steps"]
    excluded_cols += [col for col in df.columns if col.startswith("stdev_")]

    # Get numeric columns for mean/std calculation
    numeric_cols = [col for col in df.columns if col not in excluded_cols]

    # Build aggregation dictionary
    agg_dict = {}
    agg_dict.update({col: ["mean", "std"] for col in numeric_cols})
    agg_dict.update({"num_ranks": "first", "num_steps": "first"})

    # Group and aggregate
    grouped = df.groupby("experiment_id").agg(agg_dict).reset_index()

    # Flatten and rename columns
    new_columns = ["experiment_id"]
    for col in grouped.columns[1:]:  # Skip experiment_id
        if isinstance(col, tuple):
            if col[1] == "mean":
                new_columns.append(f"{col[0]}_mean")
            elif col[1] == "std":
                new_columns.append(f"{col[0]}_stdev")
            else:  # for "first"
                new_columns.append(col[0])
        else:
            new_columns.append(col)

    grouped.columns = new_columns
    return grouped


def process_deisa_data(df):
    """Process deisa data"""
    # Identify columns to exclude from mean/std calculation
    excluded_cols = ["experiment_id", "experiment_name", "num_ranks", "num_steps"]
    excluded_cols += [col for col in df.columns if col.startswith("stdev_")]

    # Get numeric columns for mean/std calculation
    numeric_cols = [col for col in df.columns if col not in excluded_cols]

    # Build aggregation dictionary
    agg_dict = {}
    agg_dict.update({col: ["mean", "std"] for col in numeric_cols})
    agg_dict.update({"num_ranks": "first", "num_steps": "first"})

    # Group and aggregate
    grouped = df.groupby("experiment_id").agg(agg_dict).reset_index()

    # Flatten and rename columns
    new_columns = ["experiment_id"]
    for col in grouped.columns[1:]:  # Skip experiment_id
        if isinstance(col, tuple):
            if col[1] == "mean":
                new_columns.append(f"{col[0]}_mean")
            elif col[1] == "std":
                new_columns.append(f"{col[0]}_stdev")
            else:  # for "first"
                new_columns.append(col[0])
        else:
            new_columns.append(col)

    grouped.columns = new_columns
    return grouped


def safe_load_csv(filepath, dataset_name):
    """Safely load CSV file with error handling"""
    try:
        df = pd.read_csv(filepath)
        print(f"Successfully loaded {dataset_name} data: {len(df)} rows")
        return df
    except FileNotFoundError:
        print(f"Warning: Unable to find data file for {dataset_name} at {filepath}")
        return None
    except Exception as e:
        print(f"Error loading {dataset_name} data: {str(e)}")
        return None


def plot_with_error_bars(fig, x, y_mean, y_std, name, color, row, col, showlegend=False):
    """Helper function to add line plot with error bars"""
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y_mean,
            mode="lines+markers",
            name=name,
            line=dict(color=color),
            showlegend=showlegend,
        ),
        row=row,
        col=col,
    )

    # Add error bars
    fig.add_trace(
        go.Scatter(
            x=list(x) + list(x)[::-1],
            y=list(y_mean + y_std) + list(y_mean - y_std)[::-1],
            fill="toself",
            fillcolor=f"rgba{tuple(list(int(color[i : i + 2], 16) for i in (1, 3, 5)) + [0.2])}",
            line=dict(color="rgba(255,255,255,0)"),
            showlegend=False,
            # hoverinfo="skip",
        ),
        row=row,
        col=col,
    )


# Load the CSV files with better error handling
parflow_df = safe_load_csv("./experiments-parflow/experiment-timings.csv", "parflow")
doreisa_df = safe_load_csv("./experiments-doreisa/experiment-timings.csv", "doreisa")
deisa_df = safe_load_csv("./experiments-deisa/experiment-timings.csv", "deisa")

# Process the data only if DataFrames exist
datasets = {}
num_steps = 0

if parflow_df is not None:
    datasets["parflow"] = process_parflow_data(parflow_df)
    print(f"Processed ParFlow data: {len(datasets['parflow'])} configurations")
    num_steps = int(datasets["parflow"]["num_steps"].iloc[0])

if doreisa_df is not None:
    datasets["doreisa"] = process_doreisa_data(doreisa_df)
    print(f"Processed Doreisa data: {len(datasets['doreisa'])} configurations")
    if num_steps == 0:
        num_steps = int(datasets["doreisa"]["num_steps"].iloc[0])
    else:
        assert int(datasets["doreisa"]["num_steps"].iloc[0]) == num_steps

if deisa_df is not None:
    datasets["deisa"] = process_deisa_data(deisa_df)
    print(f"Processed Deisa data: {len(datasets['deisa'])} configurations")
    if num_steps == 0:
        num_steps = int(datasets["deisa"]["num_steps"].iloc[0])
    else:
        assert int(datasets["deisa"]["num_steps"].iloc[0]) == num_steps

# Check if we have any data to work with
if not datasets:
    print("Error: No valid datasets found. Please check your file paths.")
    exit(1)

print(f"Working with {len(datasets)} dataset(s): {list(datasets.keys())}")
print(f"Number of steps: {num_steps}")

# Define colors for each dataset
colors = {
    "parflow": "#2c7bb6",  # Blue
    "doreisa": "#d7191c",  # Red
    "deisa": "#fdae61",  # Orange
}

# Define the specific metrics to plot as requested in comments
line_plot_metrics = [
    "simulation_total_runtime_mean",
    "richards_exclude_first_step_mean",
    "total_analytics_time_mean",
    "avg_graph_formation_time_mean",
    "avg_graph_compute_time_mean",
    "avg_pdi_init_time_mean",
    "avg_pdi_publish_time_one_step_mean",
    "avg_time_pdi_mean",
    "avg_publish_time_per_step_mean",
]

# Create main line plots (3x3 grid, using first 8 slots + box plot in 9th slot)
subplot_titles = [
    metric.replace("_", " ").title().replace(" Mean", "") for metric in line_plot_metrics
]

fig_main = make_subplots(
    rows=3,
    cols=3,
    subplot_titles=subplot_titles,
    vertical_spacing=0.12,
    horizontal_spacing=0.05,
)

# Plot each metric
for i, metric in enumerate(line_plot_metrics[:-1]):
    row = (i // 3) + 1
    col_idx = (i % 3) + 1

    stdev_metric = metric.replace("_mean", "_stdev")

    # Plot data from all available datasets for this metric
    for j, (dataset_name, df) in enumerate(datasets.items()):
        if metric in df.columns:
            y_mean = df[metric]
            y_std = df[stdev_metric] if stdev_metric in df.columns else pd.Series([0] * len(y_mean))

            plot_with_error_bars(
                fig_main,
                df["num_ranks"],
                y_mean,
                y_std,
                dataset_name.capitalize(),
                colors[dataset_name],
                row,
                col_idx,
                showlegend=(i == 0),  # Show legend only for first plot
            )

# Update layout for main plot
fig_main.update_layout(
    title_text="Experiment Performance Analysis - Average Values by Number of Ranks",
    title_x=0.5,
    height=900,
    width=1650,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

# Add box plot for avg_publish_time_step_{step}_mean to the 9th subplot (ONLY FOR DOREISA DATASET)
if "doreisa" in datasets:
    doreisa_df = datasets["doreisa"]

    # Find all avg_publish_time_step_{step}_mean columns
    step_columns = [
        col for col in doreisa_df.columns if re.match(r"avg_publish_time_step_\d+_mean", col)
    ]

    if step_columns:
        print(f"Found {len(step_columns)} step timing columns for box plot")

        # Prepare data for box plot in the 9th subplot (row=2, col=2)
        for col in sorted(step_columns):
            step_num = int(re.search(r"avg_publish_time_step_(\d+)_mean", col).group(1))
            fig_main.add_trace(
                go.Box(
                    y=doreisa_df[col],
                    name=f"Step {step_num}",
                    # boxpoints="all",
                    # jitter=0.3,
                    # pointpos=0,
                    marker_color=colors["doreisa"],
                    showlegend=False,
                ),
                row=3,
                col=3,
            )
    else:
        print("No step timing columns found in Doreisa dataset")
else:
    print("Doreisa dataset not available - skipping step timings box plot")

# Update x-axes labels
for i in range(1, 4):
    for j in range(1, 4):
        if i == 3 and j == 1:  # Box plot subplot
            fig_main.update_xaxes(title_text="Step Number", row=i, col=j)
            fig_main.update_yaxes(title_text="Time (seconds)", row=i, col=j)
        else:
            fig_main.update_xaxes(title_text="Number of Ranks", row=i, col=j)
            fig_main.update_yaxes(title_text="Time (seconds)", row=i, col=j)

# Export main plot to HTML
fig_main.write_html("./results/experiment_analysis.html")
print("Main analysis with step timings saved to 'results/experiment_analysis.html'")


# Final summary
print("\n" + "=" * 50)
print("ANALYSIS COMPLETE")
print("=" * 50)
print(f"Successfully processed {len(datasets)} dataset(s):")
for dataset_name, df in datasets.items():
    print(f"  - {dataset_name.capitalize()}: {len(df)} configurations")

print(
    f"Generated analysis with {len(line_plot_metrics)} line plot metrics and step timings box plot"
)

if not datasets:
    print("No datasets were successfully loaded!")
elif len(datasets) < 3:
    missing = set(["parflow", "doreisa", "deisa"]) - set(datasets.keys())
    print(f"Note: Missing data for: {', '.join(missing)}")
