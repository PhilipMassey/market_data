#!/bin/bash

# Determine the project root directory (parent of the scripts/ folder)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
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

# Load optional dashboard credentials (.env.dashboard) if present
if [ -f "$SCRIPT_DIR/.env.dashboard" ]; then
    set -a
    source "$SCRIPT_DIR/.env.dashboard"
    set +a
fi

# Set default port if not already set in the environment
export PORT="${PORT:-5001}"

# Check database path (optional, but helpful for debugging/logging)
if [ -n "$SQLITE_DB_PATH" ]; then
    echo "Using custom SQLITE_DB_PATH: $SQLITE_DB_PATH"
else
    DEFAULT_DB="$HOME/projects/.data/market_data.db"
    echo "Using default database: $DEFAULT_DB"
fi

echo "Starting Portfolio Dashboard on port $PORT in the background..."
echo "Open your browser and navigate to: http://127.0.0.1:$PORT"

# Run the Flask app using the virtual environment's Python interpreter with nohup
# We set PYTHONPATH to the project root so Python can resolve imports.
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export FLASK_DEBUG="${FLASK_DEBUG:-0}"
LOG_FILE="$SCRIPT_DIR/dashboard.log"
nohup .venv/bin/python portfolio/portfolio_dashboard.py > "$LOG_FILE" 2>&1 < /dev/null &
PID=$!

echo "Dashboard is running in the background (PID: $PID)."
echo "Logs are being written to: $LOG_FILE"
echo "To stop the dashboard, run: kill $PID"

