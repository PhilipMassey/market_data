# Agent Guidelines & Configuration (`agent.md`)

This document is designed to help AI agents quickly understand, configure, run, and maintain the `market_data` project.

---

## Technical Stack
- **Backend**: Python 3.11+, Flask (for Web Dashboard), Pandas, NumPy, sqlite3
- **Frontend**: HTML5, Vanilla CSS (Premium Glassmorphic Dark Theme), Vanilla JS, Chart.js (Asset Allocation Doughnut), Flatpickr (Date Picker)
- **Database**: SQLite (Normalized structure)

---

## Directory Structure
- [portfolio/](file:///Users/philipmassey/projects/market_data/portfolio/): Dashboard backend and frontend assets
  - [portfolio_dashboard.py](file:///Users/philipmassey/projects/market_data/portfolio/portfolio_dashboard.py): Flask app routes, prices query, and Money Market rollups
  - [templates/index.html](file:///Users/philipmassey/projects/market_data/portfolio/templates/index.html): HTML page template
  - [static/style.css](file:///Users/philipmassey/projects/market_data/portfolio/static/style.css): Premium glassmorphic styles
  - [static/app.js](file:///Users/philipmassey/projects/market_data/portfolio/static/app.js): JS client-side app controller
- [database/](file:///Users/philipmassey/projects/market_data/database/): SQLite database connection and migration utilities
  - [sqlite_connection.py](file:///Users/philipmassey/projects/market_data/database/sqlite_connection.py): Database connection and table schemas initialization
  - [database_utils.py](file:///Users/philipmassey/projects/market_data/database/database_utils.py): Utility queries for closing prices
- [stock_mdb/](file:///Users/philipmassey/projects/market_data/stock_mdb/): Daily close price maintenance and load utilities
- [tests/](file:///Users/philipmassey/projects/market_data/tests/): Test suite covering all modules

---

## Configuration & Environment Variables
- **`SQLITE_DB_PATH`**: Path to the target SQLite database file.
  - *Default value*: `/Users/philipmassey/projects/.data/market_data.db`
  - *Setting local override*:
    ```bash
    export SQLITE_DB_PATH="/path/to/your/market_data.db"
    ```

---

## Core Operations

### 1. Run the Web Dashboard
To start the Flask development server, execute:
```bash
FLASK_APP=portfolio.portfolio_dashboard .venv/bin/flask run --port=5000
```
Then navigate to `http://127.0.0.1:5000` to access the Valuation and Comparison views.

### 2. Run Daily Maintenance
To download and synchronize the daily close price database:
```bash
.venv/bin/python stock_mdb/market_data_close.py
```

### 3. Run the Test Suite (Only Run When Requested)
Only run the test suite if explicitly requested by the user. The test suite utilizes in-memory SQLite instances to keep unit tests isolated and safe.
- **Run all tests**:
  ```bash
  .venv/bin/pytest
  ```
- **Run a specific test**:
  ```bash
  .venv/bin/pytest tests/portfolio/test_portfolio_dashboard.py
  ```

---

## Developer Guidelines for AI Agents

### 1. Correctness & Isolation
- **Never interact with the physical database inside unit tests**. Always patch `get_sqlite_conn` and `init_sqlite_db` to use memory-backed SQLite connection fixtures (see `tests/portfolio/test_portfolio_dashboard.py` for examples).
- Do not refactor unrelated files. Follow **Surgical Edits Only** rules outlined in [CLAUDE.md](file:///Users/philipmassey/projects/market_data/CLAUDE.md) and [GEMINII.md](file:///Users/philipmassey/projects/market_data/GEMINII.md).

### 2. Front-End Assets Consistency
- If you modify `portfolio_dashboard.py` API endpoints (such as `/api/portfolio` or `/api/compare`), ensure that the fields returned match the client-side expectations in [app.js](file:///Users/philipmassey/projects/market_data/portfolio/static/app.js) and the JSON schemas verified in unit tests.
- UI styles are written in Vanilla CSS inside [style.css](file:///Users/philipmassey/projects/market_data/portfolio/static/style.css). Avoid introducing inline styles or Tailwind CSS utility classes unless specifically requested by the user.

### 3. Permissions & Host Access
- **URL & Host Access**: Access to `127.0.0.1` and `localhost` is always allowed.
- **JavaScript Execution**: You have permanent permission to execute JavaScript on `127.0.0.1` for local server rendering, testing, and calendar component validation. Do not prompt the user for permission when accessing this host.
