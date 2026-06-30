#!/bin/bash

# Determine the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Verify that the virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment (.venv) not found in $SCRIPT_DIR."
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo "Running load_missing.py..."
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
.venv/bin/python stock_mdb/load_missing.py
echo "Finished running load_missing.py."
