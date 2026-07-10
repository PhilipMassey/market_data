# SQLite Database Schema Overview

The application relies on a local SQLite database file to store market and portfolio data. 

## Database Configuration

* **Default Location**: `/Users/philipmassey/projects/.data/market_data.db` (outside the project repository to prevent git bloat).
* **Override Path**: Can be overridden by setting the `SQLITE_DB_PATH` environment variable.
* **Connection Manager**: Managed centrally in [sqlite_connection.py](file:///Users/philipmassey/projects/market_data/database/sqlite_connection.py) using the context manager `get_sqlite_conn()`.

---

## Active Tables

### 1. `market_data_close`

* **Purpose**: Stores historical daily closing prices for stock symbols.
* **Populated By**:
  * **Script**: [market_data_downloader.py](file:///Users/philipmassey/projects/market_data/market_data_downloader.py) and [market_data_close.py](file:///Users/philipmassey/projects/market_data/stock_mdb/market_data_close.py).
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
| `average_cost_basis`| `REAL` | Yes | Average buy price per share |
| `cost_basis_total` | `REAL` | Yes | Total cost basis of the position |
| `current_value` | `REAL` | Yes | Total current value of the position |
| `account_name` | `TEXT` | Yes | Account group mapping (e.g., `Stocks`, `Roth IRA`) |
| `last_price` | `REAL` | Yes | Last traded price for the asset |
| `percent_of_account`| `REAL` | Yes | Percentage weight of this holding in the account |

---

### 3. `ticker_meta_profile`

* **Purpose**: Stores company profile metadata (sector and industry) to enable portfolio grouping and ranking.
* **Populated By**:
  * **Script**: [migrate_symbol_profile_to_sqlite.py](file:///Users/philipmassey/projects/market_data/database/migrate_symbol_profile_to_sqlite.py).
  * **Data Source**: Seeking Alpha RapidAPI response details.
* **Schema Definition**:
  * **Primary Key**: `ticker` (Unique symbol profile per ticker)

| Column | SQLite Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `ticker` | `TEXT` | No | Uppercase stock ticker symbol (e.g. `GOOG`) |
| `sector` | `TEXT` | Yes | Sector name (e.g. `Technology`) |
| `industry` | `TEXT` | Yes | Industry name (e.g. `Software—Infrastructure`) |
