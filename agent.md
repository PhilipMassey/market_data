# Agent Guidelines & Configuration (`agent.md`)

This document is designed to help AI agents quickly understand, configure, run, and maintain the `market_data` project.

---

## Technical Stack
- **Backend**: Python 3.12+ (3.14 local / 3.12 on VM), Flask (Web Dashboard), Pandas, NumPy, sqlite3 (WAL mode), yfinance, gspread
- **Frontend**: HTML5, Vanilla CSS (Glassmorphic Dark Theme), Vanilla JS, Chart.js (Asset Allocation Doughnut), Flatpickr (Date Picker)
- **Database**: SQLite (`~/projects/.data/market_data.db`, stored outside the git repo)
- **Cloud Hosting**: Google Compute Engine (`market-data-vm`, `e2-micro`, Ubuntu 24.04 LTS, `us-west1-b`, project `market-data-vm-pm2026`)

---

## Directory Structure
- [portfolio/](file:///Users/philipmassey/projects/market_data/portfolio/): Dashboard backend, frontend assets, and ranking/export pipelines
  - [portfolio_dashboard.py](file:///Users/philipmassey/projects/market_data/portfolio/portfolio_dashboard.py): Flask app routes, SQLite queries, Money Market rollups, and optional HTTP Basic Auth
  - [ticker_period_ranks_data.py](file:///Users/philipmassey/projects/market_data/portfolio/ticker_period_ranks_data.py): Multi-period ranking calculations and in-memory cache
  - [holding_portfolios_update.py](file:///Users/philipmassey/projects/market_data/portfolio/holding_portfolios_update.py): Weekly Fidelity & Seeking Alpha import + Google Sheets sync
  - [templates/index.html](file:///Users/philipmassey/projects/market_data/portfolio/templates/index.html), [static/style.css](file:///Users/philipmassey/projects/market_data/portfolio/static/style.css), [static/app.js](file:///Users/philipmassey/projects/market_data/portfolio/static/app.js): Dashboard UI
- [database/](file:///Users/philipmassey/projects/market_data/database/): SQLite connection, schema init, and metadata utilities
  - [sqlite_connection.py](file:///Users/philipmassey/projects/market_data/database/sqlite_connection.py): Portable `SQLITE_DB_PATH` resolution, WAL mode connection manager, and table schemas
  - [database_utils.py](file:///Users/philipmassey/projects/market_data/database/database_utils.py): Close price & snapshot date query helpers
  - [update_ticker_metadata.py](file:///Users/philipmassey/projects/market_data/database/update_ticker_metadata.py), [sync_ticker_metadata_from_sheet.py](file:///Users/philipmassey/projects/market_data/database/sync_ticker_metadata_from_sheet.py), [delete_orphan_profiles.py](file:///Users/philipmassey/projects/market_data/database/delete_orphan_profiles.py)
- [stock_mdb/](file:///Users/philipmassey/projects/market_data/stock_mdb/): Daily close price maintenance (`load_missing.py`, `market_data_close.py`)
- [scripts/](file:///Users/philipmassey/projects/market_data/scripts/): CLI tools and VM/operations shell scripts
  - [run_dashboard.sh](file:///Users/philipmassey/projects/market_data/scripts/run_dashboard.sh), [run_load_missing.sh](file:///Users/philipmassey/projects/market_data/scripts/run_load_missing.sh)
  - [setup_vm.sh](file:///Users/philipmassey/projects/market_data/scripts/setup_vm.sh), [sync_db_vm.sh](file:///Users/philipmassey/projects/market_data/scripts/sync_db_vm.sh), [update_vm_firewall_ip.sh](file:///Users/philipmassey/projects/market_data/scripts/update_vm_firewall_ip.sh)
  - [period_rank_filter.py](file:///Users/philipmassey/projects/market_data/scripts/period_rank_filter.py), [get_period_rank_filter.py](file:///Users/philipmassey/projects/market_data/scripts/get_period_rank_filter.py), [money_market_rollup.py](file:///Users/philipmassey/projects/market_data/scripts/money_market_rollup.py), [dividends.py](file:///Users/philipmassey/projects/market_data/scripts/dividends.py)
- [utils/](file:///Users/philipmassey/projects/market_data/utils/): Shared helpers (`calendar_utils.py`, `email_utils.py`, `period_rank_utils.py`, `portfolio_utils.py`, `ticker_reader.py`, `ticker_utils.py`)
- [tests/](file:///Users/philipmassey/projects/market_data/tests/): Pytest unit test suite covering all modules

---

## Configuration & Environment Variables
- **`SQLITE_DB_PATH`**: Path to the target SQLite database file (expanded via `os.path.expanduser`).
  - *Default value*: `~/projects/.data/market_data.db`
- **`HOST` / `PORT` / `FLASK_DEBUG`**: Dashboard bind settings (defaults: `0.0.0.0`, `5001`, `1` locally / `0` via `run_dashboard.sh`).
- **`DASHBOARD_USER` / `DASHBOARD_PASSWORD`**: Optional HTTP Basic Auth credentials (loaded from `.env.dashboard` on the Google VM by `run_dashboard.sh`; left unset locally for passwordless access on `localhost` / Wi-Fi LAN).
- **`GMAIL_APP_PASSWORD` / `GMAIL_USER`**: Used by [email_utils.py](file:///Users/philipmassey/projects/market_data/utils/email_utils.py) for period rank email alerts.

---

## Core Operations

### 1. Run the Web Dashboard
- **Locally (Mac & same-Wi-Fi devices)**:
  ```bash
  .venv/bin/python portfolio/portfolio_dashboard.py
  ```
  Accessible at `http://127.0.0.1:5001` or `http://<mac-lan-ip>:5001`.
- **On the Google Cloud VM (24/7 / iPad remote access)**:
  ```bash
  ./scripts/run_dashboard.sh
  ```
  Accessible at `http://136.70.49.210:5001` (firewall rule `allow-dashboard-5001` open on `tcp:5001`, secured with HTTP Basic Auth).

### 2. Run Daily Maintenance & Scheduled Jobs
To download missing daily close prices, run the period rank filter, and send email notifications:
```bash
./scripts/run_load_missing.sh
```
This script is designed to run either locally or via `cron` on `market-data-vm` when macOS is closed.

### 3. Sync Database Between Mac and Google VM
```bash
./scripts/sync_db_vm.sh push   # Mac -> VM (atomic .backup + integrity_check)
./scripts/sync_db_vm.sh pull   # VM -> Mac
```

### 4. Run the Test Suite (Only Run When Requested)
Only run the test suite if explicitly requested by the user. The test suite utilizes in-memory SQLite instances to keep unit tests isolated and safe.
```bash
.venv/bin/python -m pytest
```

---

## Developer Guidelines for AI Agents

### 1. Correctness & Isolation
- **Never interact with the physical database inside unit tests**. Always patch `get_sqlite_conn` and `init_sqlite_db` to use memory-backed SQLite connection fixtures (see `tests/portfolio/test_portfolio_dashboard.py` for examples).
- Do not refactor unrelated files. Follow **Surgical Edits Only** rules outlined in [CLAUDE.md](file:///Users/philipmassey/projects/market_data/CLAUDE.md) and [GEMINII.md](file:///Users/philipmassey/projects/market_data/GEMINII.md).

### 2. Front-End Assets Consistency
- If you modify `portfolio_dashboard.py` API endpoints (such as `/data/portfolio`, `/data/compare`, or `/data/ticker-ranks`), ensure that the fields returned match the client-side expectations in [app.js](file:///Users/philipmassey/projects/market_data/portfolio/static/app.js) and the JSON schemas verified in unit tests.
- UI styles are written in Vanilla CSS inside [style.css](file:///Users/philipmassey/projects/market_data/portfolio/static/style.css). Avoid introducing inline styles or Tailwind CSS utility classes unless specifically requested by the user.

### 3. Permissions & Host Access
- **URL & Host Access**: Access to `127.0.0.1` and `localhost` is always allowed.
- **JavaScript Execution**: You have permanent permission to execute JavaScript on `127.0.0.1` for local server rendering, testing, and calendar component validation. Do not prompt the user for permission when accessing this host.
