import pandas as pd
import glob
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import os
import plotly.express as px
import itertools

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


def main():
    parser = argparse.ArgumentParser(description="Generate memory usage report from memlog_*.csv files.")
    parser.add_argument("log_dir", nargs="?", default=".", help="Directory containing memlog_*.csv files (default: current directory)")
    args = parser.parse_args()

    log_dir = args.log_dir
    pattern = os.path.join(log_dir, "memlog_*.csv")
    csv_files = glob.glob(pattern)

    if not csv_files:
        print(f"[!] No memlog_*.csv files found in directory: {log_dir}")
        return

    dfs = [pd.read_csv(file) for file in csv_files]
    df = pd.concat(dfs, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

    for col in ["used_bytes", "available_bytes", "free_bytes", "total_bytes"]:
        df[col.replace("_bytes", "_GB")] = df[col] / 1e9

    df.sort_values("timestamp", inplace=True)
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
                        x=host_data["timestamp"],
                        y=host_data[metric],
                        mode="lines",
                        name=shortname if show_legend else None,
                        line=dict(
                            color=style_map[host]["color"],
                            dash=style_map[host]["dash"],
                            width=style_map[host]["width"]
                            ),
                        hovertemplate=f"{shortname}<br>%{{x|%Y-%m-%d %H:%M:%S}}<br>{metric}: %{{y:.2f}} GB<extra></extra>",
                        showlegend=show_legend
                        ),
                    row=row, col=col
                    )


    fig.update_layout(
        title_text="Cluster Memory Usage Over Time",
        height=900,
        width=1400,
        legend_title="Hostnames",
        hovermode="x unified",
        template="plotly_white"
    )

    output_file = os.path.join(log_dir, "memory_report.html")
    fig.write_html(output_file)
    print(f"[✓] Memory report saved to: {output_file}")

if __name__ == "__main__":
    main()

