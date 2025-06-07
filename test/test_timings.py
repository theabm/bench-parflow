import pytest
import subprocess
import pandas as pd
import os
import numpy as np


def test_process_timings():
    """Test that process-timings.py produces the expected CSV output."""

    # Run the script (change to project root directory first)
    result = subprocess.run(
        ["python3", "./utils/process-timings.py", "./test/experiments/"],
        capture_output=True,
        text=True,
    )

    # Check that script ran successfully
    assert result.returncode == 0, f"Script failed with error: {result.stderr}"

    # Check that output file was created
    output_file = "./test/experiments/experiment-timings.csv"
    assert os.path.exists(output_file), f"Output file {output_file} was not created"

    # Load both CSV files
    generated_df = pd.read_csv(output_file)
    expected_df = pd.read_csv("test/experiments/expected-timings.csv")

    # Check that DataFrames have same shape
    assert generated_df.shape == expected_df.shape, (
        f"DataFrames have different shapes: {generated_df.shape} vs {expected_df.shape}"
    )

    # Check that column names match
    assert list(generated_df.columns) == list(expected_df.columns), (
        f"Column names don't match: {list(generated_df.columns)} vs {list(expected_df.columns)}"
    )

    # Compare values with tolerance for floating point numbers
    for col in generated_df.columns:
        if generated_df[col].dtype in ["float64", "float32"]:
            # For numeric columns, use approximate comparison
            pd.testing.assert_series_equal(
                generated_df[col],
                expected_df[col],
                check_exact=False,
                rtol=1e-3,  # relative tolerance
                atol=1e-3,  # absolute tolerance (0.001)
            )
        else:
            # For non-numeric columns, use exact comparison
            pd.testing.assert_series_equal(generated_df[col], expected_df[col])
