import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import re


def extract_ranks_from_parflow_name(experiment_name):
    """Extract ranks from parflow experiment name by multiplying first 3 numbers"""
    parts = experiment_name.split("_")
    if len(parts) >= 3:
        try:
            return int(parts[1]) * int(parts[2]) * int(parts[3])
        except (ValueError, IndexError):
            return 0
    return 0


def process_parflow_data(df):
    """Process parflow data with special handling"""
    # Extract actual ranks from experiment names
    df["actual_ranks"] = df["experiment_name"].apply(extract_ranks_from_parflow_name)
    # Set steps to 10 for all experiments
    df["actual_steps"] = 10

    # Group by actual ranks and calculate mean simulation_total_runtime
    grouped = df.groupby("actual_ranks")["simulation_total_runtime"].mean().reset_index()
    grouped.columns = ["num_ranks", "simulation_total_runtime"]

    return grouped


def process_regular_data(df):
    """Process doreisa and deisa data"""
    # Group by num_ranks and calculate means for all numeric columns except the excluded ones
    excluded_cols = ["experiment_name", "num_ranks", "num_steps", "var_init_time"]
    numeric_cols = [
        col
        for col in df.columns
        if col not in excluded_cols and df[col].dtype in ["float64", "int64"]
    ]

    # Group by num_ranks and calculate means
    grouped = df.groupby("num_ranks")[numeric_cols].mean().reset_index()

    return grouped


# Load the CSV files
parflow_df = pd.read_csv("./experiments-parflow/experiment-timings.csv")
doreisa_df = pd.read_csv("./experiments-doreisa/experiment-timings.csv")
deisa_df = pd.read_csv("./experiments-deisa/experiment-timings.csv")

# Process the data
parflow_processed = process_parflow_data(parflow_df)
doreisa_processed = process_regular_data(doreisa_df)
deisa_processed = process_regular_data(deisa_df)

# Define colors for each dataset
colors = {
    "parflow": "#1f77b4",  # Blue
    "doreisa": "#ff7f0e",  # Orange
    "deisa": "#2ca02c",  # Green
}

# Get all columns to plot (excluding the specified ones)
all_columns = (
    set(doreisa_processed.columns) | set(deisa_processed.columns) | set(parflow_processed.columns)
)
excluded_cols = {"experiment_name", "num_ranks", "num_steps", "var_init_time"}
plot_columns = [col for col in all_columns if col not in excluded_cols]

# Remove num_ranks from plot_columns as it's our x-axis
plot_columns = [col for col in plot_columns if col != "num_ranks"]

# Separate step-specific columns from other columns
step_columns = [col for col in plot_columns if col.startswith("avg_publish_time_step_")]
step_related_columns = step_columns + [
    col for col in plot_columns if col == "avg_publish_time_one_step"
]
other_columns = [
    col
    for col in plot_columns
    if not col.startswith("avg_publish_time_step_") and col != "avg_publish_time_one_step"
]

# Sort columns for consistent ordering
other_columns.sort()
step_columns.sort()

# Create subplot titles for other columns
subplot_titles = [col.replace("_", " ").title() for col in other_columns]

# Calculate grid dimensions (4x4 = 16 plots max)
n_plots = len(other_columns)
if n_plots > 16:
    other_columns = other_columns[:16]
    subplot_titles = subplot_titles[:16]
    n_plots = 16

# Create subplots in 4x4 grid for main plots
fig = make_subplots(
    rows=3,
    cols=3,
    subplot_titles=subplot_titles,
    vertical_spacing=0.1,
    horizontal_spacing=0.1,
)

# Plot each column (excluding step columns)
for i, col in enumerate(other_columns):
    row = (i // 3) + 1
    col_idx = (i % 3) + 1

    # Plot simulation_total_runtime for all three datasets (parflow has this)
    if col == "simulation_total_runtime":
        # ParFlow data
        if col in parflow_processed.columns:
            fig.add_trace(
                go.Scatter(
                    x=parflow_processed["num_ranks"],
                    y=parflow_processed[col],
                    mode="lines+markers",
                    name="ParFlow",
                    line=dict(color=colors["parflow"]),
                    showlegend=True,  # Always show ParFlow legend
                ),
                row=row,
                col=col_idx,
            )

        # Doreisa data
        if col in doreisa_processed.columns:
            fig.add_trace(
                go.Scatter(
                    x=doreisa_processed["num_ranks"],
                    y=doreisa_processed[col],
                    mode="lines+markers",
                    name="Doreisa",
                    line=dict(color=colors["doreisa"]),
                    showlegend=(i == 0),  # Show legend only once
                ),
                row=row,
                col=col_idx,
            )

        # Deisa data
        if col in deisa_processed.columns:
            fig.add_trace(
                go.Scatter(
                    x=deisa_processed["num_ranks"],
                    y=deisa_processed[col],
                    mode="lines+markers",
                    name="Deisa",
                    line=dict(color=colors["deisa"]),
                    showlegend=(i == 0),  # Show legend only once
                ),
                row=row,
                col=col_idx,
            )
    else:
        # For other columns, only plot doreisa and deisa
        # Doreisa data
        if col in doreisa_processed.columns:
            fig.add_trace(
                go.Scatter(
                    x=doreisa_processed["num_ranks"],
                    y=doreisa_processed[col],
                    mode="lines+markers",
                    name="Doreisa",
                    line=dict(color=colors["doreisa"]),
                    showlegend=(i == 0),  # Show legend only once
                ),
                row=row,
                col=col_idx,
            )

        # Deisa data
        if col in deisa_processed.columns:
            fig.add_trace(
                go.Scatter(
                    x=deisa_processed["num_ranks"],
                    y=deisa_processed[col],
                    mode="lines+markers",
                    name="Deisa",
                    line=dict(color=colors["deisa"]),
                    showlegend=(i == 0),  # Show legend only once
                ),
                row=row,
                col=col_idx,
            )

# Update layout
fig.update_layout(
    title_text="Experiment Performance Analysis - Average Values by Number of Ranks",
    title_x=0.5,
    height=900,
    width=1200,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

# Update x-axes labels
for i in range(1, 4):
    for j in range(1, 4):
        fig.update_xaxes(title_text="Number of Ranks", row=i, col=j)

# Export to HTML
fig.write_html("./results/experiment_analysis.html")

# Create separate figure for step-by-step publish times
if step_related_columns:
    # Define line styles and widths (5 styles x 2 widths = 10 combinations)
    line_styles = ["solid", "dash", "dot", "dashdot", "longdash"]
    line_widths = [2, 4]  # Two different widths
    # Create 2x1 subplot for step analysis (one for individual steps, one for overall average)
    step_fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=[
            "Average Publish Time by Individual Step",
            "Average Publish Time per Step (Overall)",
        ],
        vertical_spacing=0.15,
    )

    # Plot individual steps in the first subplot
    for i, col in enumerate(step_columns):
        step_num = col.split("_")[-1]  # Extract step number
        style_idx = i % len(line_styles)
        width_idx = i // len(line_styles)

        current_style = line_styles[style_idx]
        current_width = line_widths[width_idx] if width_idx < len(line_widths) else line_widths[0]

        # Doreisa data
        if col in doreisa_processed.columns:
            step_fig.add_trace(
                go.Scatter(
                    x=doreisa_processed["num_ranks"],
                    y=doreisa_processed[col],
                    mode="lines+markers",
                    name=f"Doreisa - Step {step_num}",
                    line=dict(color=colors["doreisa"], dash=current_style, width=current_width),
                    marker=dict(size=4),
                    legendgroup="steps",
                ),
                row=1,
                col=1,
            )

        # Deisa data
        if col in deisa_processed.columns:
            step_fig.add_trace(
                go.Scatter(
                    x=deisa_processed["num_ranks"],
                    y=deisa_processed[col],
                    mode="lines+markers",
                    name=f"Deisa - Step {step_num}",
                    line=dict(color=colors["deisa"], dash=current_style, width=current_width),
                    marker=dict(size=4),
                    legendgroup="steps",
                ),
                row=1,
                col=1,
            )

    # Plot overall average publish time per step in the second subplot
    if "avg_publish_time_one_step" in doreisa_processed.columns:
        step_fig.add_trace(
            go.Scatter(
                x=doreisa_processed["num_ranks"],
                y=doreisa_processed["avg_publish_time_one_step"],
                mode="lines+markers",
                name="Doreisa - Overall Average",
                line=dict(color=colors["doreisa"], width=3),
                marker=dict(size=8),
                legendgroup="overall",
            ),
            row=2,
            col=1,
        )

    if "avg_publish_time_one_step" in deisa_processed.columns:
        step_fig.add_trace(
            go.Scatter(
                x=deisa_processed["num_ranks"],
                y=deisa_processed["avg_publish_time_one_step"],
                mode="lines+markers",
                name="Deisa - Overall Average",
                line=dict(color=colors["deisa"], width=3),
                marker=dict(size=8),
                legendgroup="overall",
            ),
            row=2,
            col=1,
        )

    # Update step figure layout
    step_fig.update_layout(
        title_text="Step-by-Step Publish Time Analysis",
        title_x=0.5,
        height=900,
        width=1200,
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
    )

    # Update axes labels
    step_fig.update_xaxes(title_text="Number of Ranks", row=1, col=1)
    step_fig.update_xaxes(title_text="Number of Ranks", row=2, col=1)
    step_fig.update_yaxes(title_text="Publish Time (seconds)", row=1, col=1)
    step_fig.update_yaxes(title_text="Average Publish Time (seconds)", row=2, col=1)

    # Export step figure to separate HTML
    step_fig.write_html("./results/experiment_step_analysis.html")

print("Analysis complete! Main plots saved to 'results/experiment_analysis.html'")
if step_related_columns:
    print("Step-by-step analysis saved to 'results/experiment_step_analysis.html'")
print(
    f"Processed {len(other_columns)} main variables and {len(step_related_columns)} step-related variables across 3 datasets"
)
print(f"ParFlow data: {len(parflow_processed)} rank configurations")
print(f"Doreisa data: {len(doreisa_processed)} rank configurations")
print(f"Deisa data: {len(deisa_processed)} rank configurations")

