# Project Overview

This document provides a high-level overview of the architecture and code modules in the `market_data` project.

---

## System Architecture

`market_data` runs on two environments sharing the same codebase and SQLite database schema (`~/projects/.data/market_data.db`):

1. **Local Mac (`~/projects/market_data`)**: Used for development, interactive Jupyter analysis, processing local Fidelity/Seeking Alpha exports from `~/Downloads`, and local/Wi-Fi LAN dashboard access (`http://localhost:5001` or `http://<lan-ip>:5001`).
2. **Google Cloud VM (`market-data-vm` · `136.70.49.210`)**: An `e2-micro` Ubuntu 24.04 LTS instance in `us-west1-b` (GCP project `market-data-vm-pm2026`). It exists for two purposes:
   - **Unattended Scheduling**: Running daily market close updates (`scripts/run_load_missing.sh`) and period-rank alerts via `cron` even when macOS is asleep or closed.
   - **Remote / iPad Dashboard Access**: Serving the Flask Portfolio Valuation Dashboard 24/7 on `http://136.70.49.210:5001` (GCP firewall rule `allow-dashboard-5001` on `tcp:5001`, protected by HTTP Basic Auth via `.env.dashboard`).

The local and VM databases are kept in sync using `./scripts/sync_db_vm.sh push|pull`, which takes an atomic SQLite `.backup` snapshot and verifies `PRAGMA integrity_check` over `gcloud compute ssh`/`scp`.

---

## Modules

### `database/`
- **[sqlite_connection.py](file:///Users/philipmassey/projects/market_data/database/sqlite_connection.py)**: Portable `SQLITE_DB_PATH` resolution (`os.path.expanduser`), `get_sqlite_conn()` context manager with `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`, and `init_sqlite_db()` schema initialization.
- **[database_utils.py](file:///Users/philipmassey/projects/market_data/database/database_utils.py)**: Query helpers (`get_close_price_records`, `get_latest_price`, `get_price_at_date`, `get_latest_snapshot_date_on_or_before`).
- **[update_ticker_metadata.py](file:///Users/philipmassey/projects/market_data/database/update_ticker_metadata.py)** & **[sync_ticker_metadata_from_sheet.py](file:///Users/philipmassey/projects/market_data/database/sync_ticker_metadata_from_sheet.py)**: Populate and synchronize `ticker_meta_profile` from Yahoo Finance or Google Sheets.
- **[delete_orphan_profiles.py](file:///Users/philipmassey/projects/market_data/database/delete_orphan_profiles.py)**: Removes metadata entries for tickers no longer present in `tickers/`.

### `stock_mdb/`
- **[market_data_close.py](file:///Users/philipmassey/projects/market_data/stock_mdb/market_data_close.py)**: Finds missing business-day close prices across the past year (`pandas_market_calendars` NYSE calendar) and batch-downloads them from `yfinance` into `market_data_close`.
- **[load_missing.py](file:///Users/philipmassey/projects/market_data/stock_mdb/load_missing.py)**: Daily pipeline entrypoint that runs `download_and_insert_missing_close_prices()`, clears the ranking cache, executes `run_period_rank_filter()`, and sends an email summary via `send_period_rank_email()`.

### `portfolio/`
- **[portfolio_dashboard.py](file:///Users/philipmassey/projects/market_data/portfolio/portfolio_dashboard.py)**: Flask backend serving the Valuation, Comparison, and Ticker Ranks views (`/data/portfolio`, `/data/compare`, `/data/snapshot-dates`, `/data/business-days`, `/data/ticker-ranks`, `/data/ticker-ranks/detail`). Binds to `0.0.0.0:5001` by default and enforces HTTP Basic Auth when `DASHBOARD_PASSWORD` is set.
- **[ticker_period_ranks_data.py](file:///Users/philipmassey/projects/market_data/portfolio/ticker_period_ranks_data.py)** & **[ticker_period_ranked_coarse.py](file:///Users/philipmassey/projects/market_data/portfolio/ticker_period_ranked_coarse.py)**: Computes multi-period returns, risk-reward ranks, relative strength industry ranks, stretch scores, and Kelly fraction ranks.
- **[holding_portfolios_update.py](file:///Users/philipmassey/projects/market_data/portfolio/holding_portfolios_update.py)** & **[load_holding_portfolios.py](file:///Users/philipmassey/projects/market_data/portfolio/load_holding_portfolios.py)**: Weekly import of Seeking Alpha `.xlsx` exports and Fidelity `Portfolio_Positions_*.csv` snapshots into `tickers/` CSVs, SQLite `fidelity_positions`, and Google Sheets (`update_portfolio_adjustments.py`).

### `scripts/`
- **VM & Deployment**: [setup_vm.sh](file:///Users/philipmassey/projects/market_data/scripts/setup_vm.sh), [sync_db_vm.sh](file:///Users/philipmassey/projects/market_data/scripts/sync_db_vm.sh), [run_dashboard.sh](file:///Users/philipmassey/projects/market_data/scripts/run_dashboard.sh), [run_load_missing.sh](file:///Users/philipmassey/projects/market_data/scripts/run_load_missing.sh), [update_vm_firewall_ip.sh](file:///Users/philipmassey/projects/market_data/scripts/update_vm_firewall_ip.sh).
- **Analytics & Utilities**: [period_rank_filter.py](file:///Users/philipmassey/projects/market_data/scripts/period_rank_filter.py), [get_period_rank_filter.py](file:///Users/philipmassey/projects/market_data/scripts/get_period_rank_filter.py), [money_market_rollup.py](file:///Users/philipmassey/projects/market_data/scripts/money_market_rollup.py), [dividends.py](file:///Users/philipmassey/projects/market_data/scripts/dividends.py).
