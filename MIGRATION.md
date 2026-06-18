# Database Migration Steps (MongoDB to SQLite)

This document outlines the completed and proposed migration steps to transition the project databases from MongoDB to SQLite.

---

## Part 1: SQLite Daily Close Price Migration (Completed)

1. **Verify MongoDB Connection**: Ensure the local MongoDB database containing `stock_market` is accessible and running.
2. **Initialize SQLite Database Schema**: Create the local target directory (`/Users/philipmassey/projects/.data/`) and initialize the SQLite database table `market_data_close` with keys `(date, ticker, close_price)`.
3. **Run Migration Script**: Execute `database/migrate_to_sqlite.py` to:
   - Extract daily close price records from the MongoDB `market_data_close` collection.
   - Parse wide-format documents (containing nested ticker columns per date) into normalized rows.
   - Filter out invalid values (such as `NaN` or non-numeric types).
   - Perform bulk insertions/upserts into the SQLite table.
4. **Refactor Codebase to use SQLite**:
   - Update `market_data_downloader.py` to write directly to the SQLite `market_data_close` table instead of MongoDB.
   - Update daily maintenance procedures in `stock_mdb/market_data_close.py` to sync with the SQLite database.
5. **Clean up configuration/guidelines**:
   - Remove `pymongo` and `mongomock` from `requirements.txt`.
   - Update command and architecture details in `CLAUDE.md` and `GEMINII.md`.

---

## Part 2: Future Module Re-implementation Steps (Proposed)

For each of the remaining MongoDB collections (`FidelityPositions`, `symbol_profile`, `symbol_info`, `market_data_volume`):

### 1. Fidelity Positions (CSV Portfolio Updates)
1. **Initialize Table Schema**: Create a SQLite table `fidelity_positions` with columns for date, symbol, quantity, average cost basis, cost basis total, and current value.
2. **Refactor CSV Import**: Update the portfolio csv import module to parse Fidelity export CSVs and insert records using `INSERT OR REPLACE` into the SQLite table.

### 2. Daily Trading Volume
1. **Initialize Table Schema**: Create a SQLite table `market_data_volume` with columns `(date, ticker, volume)`.
2. **Refactor yfinance downloader**: Update volume downloaders to store yfinance data in SQLite instead of MongoDB.

### 3. Seeking Alpha Profiles & Analytics
1. **Initialize Table Schema**: Create SQLite tables `symbol_profiles` and `symbol_info`. Use a text/JSON column in `symbol_profiles` to store nested description and company metadata.
2. **Refactor Fetchers**: Update RapidAPI seeking alpha integration script to write parsed profiles and financial indicators directly to SQLite.
