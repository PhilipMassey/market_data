# Project Overview

This document provides a high-level overview of the code modules in the `market_data` project.

## Modules

### `market_data_downloader.py`

*   **Purpose**: This module is responsible for downloading daily stock market data and storing it in a SQLite database.
*   **Functionality**:
    *   Connects to a local SQLite database file.
    *   Uses the `yfinance` library to download the daily close price for specified stock tickers.
    *   Downloads data only for business days.
    *   Stores the data in the `market_data_close` table.

### `portfolio/holding_portfolios_update.py`

*   **Purpose**: Manages the weekly portfolio updating, synchronization, and comparison pipeline.
*   **Functionality**:
    *   **Seeking Alpha Excel Import**: Scans `~/Downloads` for Seeking Alpha Excel exports (`* YYYY-MM-DD.xlsx`). Selects the latest version by date, extracts unique ticker symbols from the `Symbol` column, sorts them alphabetically, and writes them to single-column CSVs. Files starting with `"Current "` are written to `tickers/Holding/`, and all other files are written to `tickers/Seeking_Alpha/`.
    *   **Fidelity CSV Import**: Scans `~/Downloads` for exactly one `Portfolio_Positions_*.csv` file, parses and cleans the positions, and inserts them into the SQLite database. It also extracts ticker symbols grouped by account name into `tickers/Holding/<Mapped Account>.csv`, automatically rolling up sub-accounts (e.g. `'Stocks'` & `'X Stocks'` into `'Stocks'`, and `'ETFs Roth'` & `'Z ETFs'` into `'ETFs'`) and excluding cash/core positions.
    *   **Holdings Comparison**: Compares the Seeking Alpha targets (`Current <Category>.csv`) against actual Fidelity holdings (`<Category>.csv`) in `tickers/Holding/` and writes a detailed mismatches report to `~/Downloads/mismatches.txt`.

