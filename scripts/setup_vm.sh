#!/bin/bash
set -euo pipefail

# Bootstrap script to run on a fresh Ubuntu/Debian Google Compute Engine VM
# Usage on the VM:
#   ./scripts/setup_vm.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$SCRIPT_DIR"

echo "1. Updating system packages and installing Python & SQLite dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip sqlite3 git rsync

echo "2. Ensuring data directory $HOME/projects/.data exists..."
mkdir -p "$HOME/projects/.data"

echo "3. Setting up Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo "4. Initializing SQLite schema if database is not yet uploaded..."
PYTHONPATH="$SCRIPT_DIR" .venv/bin/python -c "from database.sqlite_connection import init_sqlite_db, SQLITE_DB_PATH; init_sqlite_db(); print('Initialized DB at:', SQLITE_DB_PATH)"

echo "VM setup complete!"
echo "To start the dashboard on the VM, run: ./scripts/run_dashboard.sh"

