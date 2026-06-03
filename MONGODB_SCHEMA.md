# MongoDB Schema and Population Overview

The application relies on a local MongoDB instance. All primary data is stored within the `stock_market` database inside several distinct collections. 
A Singleton Connection manager is used to connect to the DB string: `client = MongoClient()`.

Here is an outline of the collections and the scripts responsible for populating them.

## Database: `stock_market`

### 1. `FidelityPositions` (`md.db_fidel_pos`)
*   **Purpose**: Stores historical and current snapshots of your Fidelity investment portfolios. It keeps track of the symbols, quantity, value, and cost basis per account.
*   **Populated By**: 
    *   **Workflow**: The Weekly Fidelity Pipeline (`/weekly-fidelity-flow`).
    *   **Script**: `market_data/portfolio/holding_portfolios_update.py` 
    *   **Data Source**: The script parses your downloaded `Portfolio_Positions[...].csv` (exported from Fidelity Investments), aggregates the current holdings, tags them with the export date, and inserts the data row-by-row into this collection.

### 2. `market_data_close` (`md.db_close`)
*   **Purpose**: Stores the historical daily closing prices for all tracked stock symbols. Data is structured chronologically to allow performance measurements.
*   **Populated By**:
    *   **Script**: Data loading and missing value scripts, primarily `market_data/stock_mdb/load_missing.py`.
    *   **Data Source**: It queries the Yahoo Finance API (`md.get_yahoo_ndays_ago`) to fetch the historical close price data for symbols that are missing data on specific trading days.

### 3. `market_data_volume` (`md.db_volume`)
*   **Purpose**: Stores historical daily trading volume data for tracked stock symbols. 
*   **Populated By**:
    *   Currently, explicit updates to volume via `load_missing.py` are sporadically toggled, but it canonically follows the exact same population pattern and source (Yahoo Finance) as `market_data_close`.

### 4. `symbol_profile` (`md.db_symbol_profile`)
*   **Purpose**: Stores essential company profiling data—most importantly the `sector` and `industry` strings for each stock symbol. This allows the Dash applications to group portfolio performance by sector/industry.
*   **Populated By**:
    *   **Script**: `apis/seeking_alpha/update_symbol_profile.py`
    *   **Data Source**: Fetches company data from the Seeking Alpha API (usually routed through RapidAPI).

### 5. `symbol_profile_cache` (`md.db_symbol_profile_cache`)
*   **Purpose**: Acts as a staging or caching database for symbol profiles. Because API calls can be rate-limited or take a long time to refresh weekly, data is cached here first.
*   **Populated By**:
    *   **Script**: `update_symbol_profile.py` uses this to temporarily hold data during its weekly refresh logic before fully synchronizing the cleaned output into the primary `symbol_profile` collection.

### 6. `symbol_info` (`md.db_symbol_info`)
*   **Purpose**: Stores extended analytics and financial metric identifiers originally from Seeking Alpha.
*   **Populated By**: 
    *   **Script**: `apis/seeking_alpha/update_symbol_info.py`. 
    *   **Data Source**: Runs iterative API calls to Seeking Alpha to pull down granular financial information per symbol.

### Minor / Testing Collections
*   `test_close` (`md.db_test_close`) & `test_volume` (`md.db_test_vol`): Temporary sandboxed collections used to test data parsing and formatting logic before modifying production DBs.
