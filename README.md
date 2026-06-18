# market_data

Simplest approach to investment in equities.

## Developer Setup

### 1. Virtual Environment Activation
To run Python scripts or tests with project-specific dependencies, you must activate the virtual environment:
```bash
# From the project root:
source .venv/bin/activate
```
*(Once activated, you will see `(.venv)` in your terminal prompt).*

### 2. Running the Test Suite
The testing framework configured is `pytest`. You can run the tests using:
```bash
# Run the entire test suite
.venv/bin/pytest

# Run a specific test file
.venv/bin/pytest tests/stock_mdb/test_market_data_close.py
```

### 3. Database Setup (SQLite)
This project uses SQLite for storing daily close prices (`market_data_close`).
Configured via `os.environ.get('SQLITE_DB_PATH')` (defaults to `/Users/philipmassey/projects/.data/market_data.db`).
