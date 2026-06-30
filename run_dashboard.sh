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

# Set default port if not already set in the environment
export PORT="${PORT:-5001}"

# Check database path (optional, but helpful for debugging/logging)
if [ -n "$SQLITE_DB_PATH" ]; then
    echo "Using custom SQLITE_DB_PATH: $SQLITE_DB_PATH"
else
    # Determine default DB path based on database/sqlite_connection.py logic
    LOCAL_DB="$SCRIPT_DIR/database/market_data.db"
    DEFAULT_DB="/Users/philipmassey/projects/.data/market_data.db"
    if [ -f "$LOCAL_DB" ]; then
        echo "Using local database: $LOCAL_DB"
    else
        echo "Using default database: $DEFAULT_DB"
    fi
fi

echo "Starting Portfolio Dashboard on port $PORT in the background..."
echo "Open your browser and navigate to: http://127.0.0.1:$PORT"

# Run the Flask app using the virtual environment's Python interpreter with nohup
# We set PYTHONPATH to the project root so Python can resolve imports.
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
LOG_FILE="$SCRIPT_DIR/dashboard.log"
nohup .venv/bin/python portfolio/portfolio_dashboard.py > "$LOG_FILE" 2>&1 &
PID=$!

echo "Dashboard is running in the background (PID: $PID)."
echo "Logs are being written to: $LOG_FILE"
echo "To stop the dashboard, run: kill $PID"

