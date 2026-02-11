#!/bin/bash

# USGS Streamflow Dashboard Startup Script

echo "=== USGS Streamflow Dashboard ==="
echo "Starting dashboard application..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the dashboard directory
cd "$SCRIPT_DIR"

# Check if we're in the correct directory
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH."
    exit 1
fi

# Install requirements if needed
if [ ! -d "__pycache__" ]; then
    echo "Installing required packages..."
    pip install -r requirements.txt
    echo ""
fi

# Set Python path to include parent directory (for streamflow_analyzer import)
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

echo "Starting dashboard on http://localhost:8050"
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application
python3 app.py
