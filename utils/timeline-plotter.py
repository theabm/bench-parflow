"""
MPI Event Timeline Analyzer
Parses log files from distributed applications and creates timeline visualizations
for SIM, PDI, and DOREISA events.
"""

import argparse
import os
import re
import glob
import plotly.graph_objects as go


class EventParser:
    def __init__(self, target_rank):
        self.target_rank = target_rank
        self.sim_events = []
        self.pdi_events = []
        self.doreisa_events = []

    def parse_log_file(self, file_path):
        """Parse the log file and extract events for the target rank."""
        print(f"Parsing log file: {file_path}")

        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse SIM events
                    if line.startswith("[SIM,"):
                        self._parse_sim_event(line)

                    # Parse PDI events
                    elif line.startswith("[PDI,"):
                        self._parse_pdi_event(line)

                    # Parse DOREISA events
                    elif line.startswith("[DOREISA,"):
                        self._parse_doreisa_event(line)

                except Exception as e:
                    print(f"Warning: Error parsing line {line_num}: {line}")
                    print(f"Error: {e}")
                    continue

    def _parse_sim_event(self, line):
        """Parse SIM event line."""
        # Pattern: [SIM, EVENT_TYPE, RANK] START : time END : time DIFF: diff [ITER: iter]
        sim_pattern = r"\[SIM,\s*([^,]+),\s*(\d+)\]\s*START\s*:\s*([\d.]+)\s*END\s*:\s*([\d.]+),?\s*DIFF:\s*([\d.]+)(?:\s*ITER:\s*(\d+))?"

        match = re.match(sim_pattern, line)
        if match:
            event_type, rank, start_time, end_time, diff, iteration = match.groups()
            rank = int(rank)

            # Only process events for the target rank
            if rank == self.target_rank:
                event_data = {
                    "type": event_type.strip(),
                    "rank": rank,
                    "start": float(start_time),
                    "end": float(end_time),
                    "diff": float(diff),
                    "iteration": int(iteration) if iteration else None,
                }
                self.sim_events.append(event_data)

    def _parse_pdi_event(self, line):
        """Parse PDI event line."""
        # Pattern: [PDI, EVENT_TYPE, RANK] START: time END: time DIFF: diff [ITER: iter] [QUANT: quant]
        pdi_pattern = r"\[PDI,\s*([^,]+),\s*(\d+)\]\s*START:\s*([\d.]+)\s*END:\s*([\d.]+)\s*DIFF:\s*([\d.]+)(?:\s*ITER:\s*(\d+))?(?:\s*QUANT:\s*([^\s]+))?"

        match = re.match(pdi_pattern, line)
        if match:
            event_type, rank, start_time, end_time, diff, iteration, quantity = (
                match.groups()
            )
            rank = int(rank)

            # Only process events for the target rank
            if rank == self.target_rank:
                event_data = {
                    "type": event_type.strip(),
                    "rank": rank,
                    "start": float(start_time),
                    "end": float(end_time),
                    "diff": float(diff),
                    "iteration": int(iteration) if iteration else None,
                    "quantity": quantity if quantity else None,
                }
                self.pdi_events.append(event_data)

    def _parse_doreisa_event(self, line):
        """Parse DOREISA event line."""
        # Pattern: [DOREISA, ITER] START : time END : time DIFF : diff
        doreisa_pattern = r"\[DOREISA,\s*(\d+)\]\s*START\s*:\s*([\d.]+)\s*END\s*:\s*([\d.]+)\s*DIFF\s*:\s*([\d.]+)"

        match = re.match(doreisa_pattern, line)
        if match:
            iteration, start_time, end_time, diff = match.groups()

            event_data = {
                "iteration": int(iteration),
                "start": float(start_time),
                "end": float(end_time),
                "diff": float(diff),
            }
            self.doreisa_events.append(event_data)


def create_timeline_plot(parser, output_file):
    """Create a timeline plot using Plotly."""
    print("Creating timeline plot...")

    fig = go.Figure()

    # Colors for different event types
    colors = {"SIM": "black", "PDI": "black", "DOREISA": "black"}
    iter_colors = {
        0: "#a6cee3",
        1: "#1f78b4",
        2: "#b2df8a",
        3: "#33a02c",
        4: "#fb9a99",
        5: "#e31a1c",
        6: "#fdbf6f",
        7: "#ff7f00",
        8: "#cab2d6",
        9: "#6a3d9a",
    }

    y_positions = {"SIM": 3, "PDI": 2, "DOREISA": 1}

    print(f"{parser.sim_events=}\n\n {parser.pdi_events=}\n\n {parser.doreisa_events=}")

    # Add SIM events
    for event in parser.sim_events:
        if event["type"] == "LOOP-IO":
            continue

        event_name = f"SIM-{event['type']}"
        if event["type"] in ["LOOP-WHOLE", "EXTERN LOOP"]:
            continue
        if event["iteration"] is not None:
            event_name += f" (Iter {event['iteration']})"
            color = iter_colors[event["iteration"]]
            fig.add_vrect(
                x0=event["start"],
                x1=event["end"],
                annotation_text=event["iteration"],
                annotation_position="top",
                fillcolor=color,
                opacity=0.2,
            )
        else:
            color = colors["SIM"]

        fig.add_trace(
            go.Scatter(
                x=[event["start"], event["end"]],
                y=[y_positions["SIM"], y_positions["SIM"]],
                mode="lines+markers",
                line=dict(color=color, width=6),
                marker=dict(size=8),
                name=event_name,
                hovertemplate=f"<b>{event_name}</b><br>"
                + f"Start: {event['start']:.6f}<br>"
                + f"End: {event['end']:.6f}<br>"
                + f"Duration: {event['diff']:.6f}s<br>"
                + "<extra></extra>",
                showlegend=True,
            )
        )

    # Add PDI events
    for event in parser.pdi_events:
        event_name = f"PDI-{event['type']}"
        if event["iteration"] is not None:
            event_name += f" (Iter {event['iteration']})"
            color = iter_colors[event["iteration"]]
        else:
            color = colors["PDI"]

        # if event["quantity"]:
        #     event_name += f" [{event['quantity']}]"

        fig.add_trace(
            go.Scatter(
                x=[event["start"], event["end"]],
                y=[y_positions["PDI"], y_positions["PDI"]],
                mode="lines+markers",
                line=dict(color=color, width=6),
                marker=dict(size=8),
                name=event_name,
                hovertemplate=f"<b>{event_name}</b><br>"
                + f"Start: {event['start']:.6f}<br>"
                + f"End: {event['end']:.6f}<br>"
                + f"Duration: {event['diff']:.6f}s<br>"
                + "<extra></extra>",
                showlegend=True,
            )
        )

    # Add DOREISA events
    for event in parser.doreisa_events:
        event_name = f"DOREISA (Iter {event['iteration']})"
        color = iter_colors[event["iteration"]]

        fig.add_trace(
            go.Scatter(
                x=[event["start"], event["end"]],
                y=[y_positions["DOREISA"], y_positions["DOREISA"]],
                mode="lines+markers",
                line=dict(color=color, width=6),
                marker=dict(size=8),
                name=event_name,
                hovertemplate=f"<b>{event_name}</b><br>"
                + f"Start: {event['start']:.6f}<br>"
                + f"End: {event['end']:.6f}<br>"
                + f"Duration: {event['diff']:.6f}s<br>"
                + "<extra></extra>",
                showlegend=True,
            )
        )

    # Update layout
    fig.update_layout(
        title=f"Event Timeline for Rank {parser.target_rank}",
        xaxis_title="Time (seconds)",
        yaxis_title="Event Type",
        yaxis=dict(
            tickmode="array",
            tickvals=[1, 2, 3],
            ticktext=["DOREISA", "PDI", "SIM"],
            range=[0.5, 3.5],
        ),
        hovermode="closest",
        # width=1200,
        # height=600,
        showlegend=True,
        # legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
    )
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)

    # Save the plot
    fig.write_html(output_file)
    print(f"Timeline plot saved to: {output_file}")

    # Print summary statistics
    print(f"\nSummary for Rank {parser.target_rank}:")
    print(f"  SIM events: {len(parser.sim_events)}")
    print(f"  PDI events: {len(parser.pdi_events)}")
    print(f"  DOREISA events: {len(parser.doreisa_events)}")


def find_log_file(directory, rank=None):
    """Find the R-*.o log file in the specified directory."""
    pattern = os.path.join(directory, "R-*.o")
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError(f"No R-*.o files found in directory: {directory}")

    if len(files) > 1:
        print(f"Multiple R-*.o files found: {files}")
        print("Using the first one...")

    return files[0]


def main():
    parser = argparse.ArgumentParser(
        description="Parse MPI application logs and create event timeline visualization"
    )
    parser.add_argument(
        "directory", type=str, help="Directory containing the R-*.o log file"
    )
    parser.add_argument(
        "--rank", type=int, default=0, help="Rank to track (for SIM and PDI events)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output HTML file path (default: timeline_rank_<rank>.html)",
    )

    args = parser.parse_args()

    # Validate directory
    if not os.path.isdir(args.directory):
        print(f"Error: Directory does not exist: {args.directory}")
        return 1

    # Find log file
    try:
        log_file = find_log_file(args.directory)
        print(f"Found log file: {log_file}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # Set output file
    if args.output is None:
        args.output = f"timeline_rank_{args.rank}.html"

    # Parse events
    event_parser = EventParser(args.rank)
    event_parser.parse_log_file(log_file)

    # Create visualization
    create_timeline_plot(event_parser, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
