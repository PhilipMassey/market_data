# SQLite Database Schema Overview

The application relies on a SQLite database file to store market, portfolio, metadata, and ranking filter data. The same database schema runs locally on macOS and on the Google Cloud VM (`market-data-vm`).

## Database Configuration

* **Default Location**: `~/projects/.data/market_data.db` (outside the project repository to prevent git bloat; resolves to `/Users/<user>/projects/.data/market_data.db` on macOS and `/home/<user>/projects/.data/market_data.db` on the Linux VM).
* **Override Path**: Can be overridden by setting the `SQLITE_DB_PATH` environment variable (`os.path.expanduser()` is applied automatically).
* **Concurrency**: `get_sqlite_conn()` enables `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` so background scheduled jobs and the web dashboard can access the database safely.
* **Connection Manager**: Managed centrally in [sqlite_connection.py](file:///Users/philipmassey/projects/market_data/database/sqlite_connection.py) using the context manager `get_sqlite_conn()`.
* **VM Sync**: Synchronized between macOS and `market-data-vm` using [sync_db_vm.sh](file:///Users/philipmassey/projects/market_data/scripts/sync_db_vm.sh) (`sqlite3 .backup` + `PRAGMA integrity_check`).

---

## Active Tables

### 1. `market_data_close`

* **Purpose**: Stores historical daily closing prices for stock tickers.
* **Populated By**:
  * **Script**: [load_missing.py](file:///Users/philipmassey/projects/market_data/stock_mdb/load_missing.py) and [market_data_close.py](file:///Users/philipmassey/projects/market_data/stock_mdb/market_data_close.py).
  * **Data Source**: Yahoo Finance API via the `yfinance` Python library.
* **Schema Definition**:
  * **Primary Key**: `(date, ticker)`
  * **Indexes**: `idx_market_data_close_ticker` on `ticker` (for fast symbol lookups).

| Column | SQLite Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `date` | `TEXT` | No | ISO date format (`YYYY-MM-DD`) |
| `ticker` | `TEXT` | No | Uppercase stock ticker symbol (e.g. `AAPL`) |
| `close_price` | `REAL` | No | Daily closing price in USD |

---

### 2. `fidelity_positions`

* **Purpose**: Stores historical and current account position snapshots imported from Fidelity CSV exports.
* **Populated By**:
  * **Script**: [holding_portfolios_update.py](file:///Users/philipmassey/projects/market_data/portfolio/holding_portfolios_update.py).
  * **Data Source**: Fidelity CSV exports (e.g., `Portfolio_Positions_*.csv`).
* **Schema Definition**:
  * **Primary Key**: `(date, symbol)`
  * **Indexes**:
    * `idx_fidelity_positions_symbol` on `symbol`
    * `idx_fidelity_positions_date` on `date`

| Column | SQLite Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `date` | `TEXT` | No | ISO date format (`YYYY-MM-DD`) |
| `symbol` | `TEXT` | No | Ticker symbol (e.g. `MSFT`) or cash sweep designation (e.g. `SPAXX**`) |
| `quantity` | `REAL` | Yes | Total shares or contracts held |
| `average_cost_basis` | `REAL` | Yes | Average buy price per share |
| `cost_basis_total` | `REAL` | Yes | Total cost basis of the position |
| `current_value` | `REAL` | Yes | Total current value of the position |
| `account_name` | `TEXT` | Yes | Account group mapping (e.g., `Stocks`, `Dividends`) |
| `last_price` | `REAL` | Yes | Last traded price for the asset |
| `percent_of_account` | `REAL` | Yes | Percentage weight of this holding in the account |

---

### 3. `ticker_meta_profile`

* **Purpose**: Stores company profile metadata (company name, quote type, sector, and industry) to enable portfolio grouping and ranking.
* **Populated By**:
  * **Scripts**: [update_ticker_metadata.py](file:///Users/philipmassey/projects/market_data/database/update_ticker_metadata.py) and [sync_ticker_metadata_from_sheet.py](file:///Users/philipmassey/projects/market_data/database/sync_ticker_metadata_from_sheet.py).
  * **Data Source**: Yahoo Finance (`yfinance`) and Google Sheets metadata tab.
* **Schema Definition**:
  * **Primary Key**: `ticker` (Unique symbol profile per ticker)

| Column | SQLite Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `ticker` | `TEXT` | No | Uppercase stock ticker symbol (e.g. `GOOG`) |
| `company_name` | `TEXT` | Yes | Company or fund name |
| `type` | `TEXT` | Yes | Asset type (e.g. `EQUITY`, `ETF`) |
| `sector` | `TEXT` | Yes | Sector name (e.g. `Technology`) |
| `industry` | `TEXT` | Yes | Industry name (e.g. `Software—Infrastructure`) |

---

### 4. `period_rank_filter`

* **Purpose**: Persists daily filtered ticker lists across cumulative period steps so day-over-day additions and removals can be tracked and emailed.
* **Populated By**:
  * **Scripts**: [period_rank_filter.py](file:///Users/philipmassey/projects/market_data/scripts/period_rank_filter.py) (via `load_missing.py`) and [period_rank_utils.py](file:///Users/philipmassey/projects/market_data/utils/period_rank_utils.py).
* **Schema Definition**:
  * **Primary Key**: `(date, period_step)`

| Column | SQLite Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `date` | `TEXT` | No | Snapshot business date (`YYYY-MM-DD`) |
| `period_step` | `TEXT` | No | Ordinal step label (e.g. `1st`, `2nd`, `3rd`) |
| `date_range` | `TEXT` | Yes | Combined date span (`YYYY-MM-DD to YYYY-MM-DD`) |
| `tickers` | `TEXT` | No | Space-separated list of qualifying tickers |
