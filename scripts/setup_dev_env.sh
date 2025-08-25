#!/bin/bash

set -e

cd "$(dirname "$(dirname "$(realpath "$0")")")"

# Check if the 'uv' command is available
if ! command -v uv &> /dev/null; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "No virtual environment found (venv or .venv)."
        echo "You can manually install 'uv' and then call this script."
        echo "Aborting."
        exit 1
    fi

    if ! command -v pip &> /dev/null; then
        echo "pip not found in the virtual environment. Aborting."
        exit 1
    fi

    echo "Installing 'uv' via pip..."
    pip install uv
fi

# Clean up any previous build
rm -rf nomad/app/static/gui

# Install nomad
uv pip install -e ".[infrastructure,parsing,dev]" -c requirements-dev.txt

uv pip install -r requirements-plugins.txt # todo: remove this after moving to distro

# Generate .env file for the GUI
python -m nomad.cli dev gui-env > gui/.env.development
