#!/bin/bash
set -xeu

# Determine the project root directory
PROJECT_ROOT=$(dirname $(dirname $(dirname $(readlink -f "${BASH_SOURCE[0]}"))))

# Define the path to the virtual environment
VENV_PATH="$PROJECT_ROOT/.venv"

# Define the path to the requirements.txt file
REQUIREMENTS_PATH="$(dirname $(readlink -f "${BASH_SOURCE[0]}"))/requirements.txt"

# Remove any existing virtual environment
rm -rf "$VENV_PATH"

# Create the virtual environment
python3 -m venv "$VENV_PATH"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Install the requirements
python3 -m pip install -r "$REQUIREMENTS_PATH"

# TODO: after running this script, pressing tab for completion undoes the environment activation 
# as well as the guix shell