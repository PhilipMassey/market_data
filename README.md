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

### 3. Databases Setup (Dual Configuration)
This project uses a dual-database architecture:
*   **MongoDB**: Used for storing symbol profiles and portfolio positions (`symbol_profile`, `FidelityPositions`, etc.). Configured via `os.environ.get('MONGO_URI')`.
*   **SQLite**: Used for storing daily close prices (`market_data_close`). Configured via `os.environ.get('SQLITE_DB_PATH')` (defaults to `/Users/philipmassey/projects/.data/market_data.db`).

### 4. Migrating Close Prices from MongoDB to SQLite
If you need to migrate your existing historical close prices from your local MongoDB instance to the SQLite database, run:
```bash
.venv/bin/python database/migrate_to_sqlite.py
```
This script automatically transforms the wide MongoDB format into the SQLite normalized schema and handles missing or invalid (`NaN`) values safely.
