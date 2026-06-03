# Project Overview

This document provides a high-level overview of the code modules in the `market_data` project.

## Modules

### `market_data_downloader.py`

*   **Purpose**: This module is responsible for downloading daily stock market data and storing it in a MongoDB database.
*   **Functionality**:
    *   Connects to a local MongoDB instance.
    *   Uses the `yfinance` library to download the daily close price for specified stock tickers.
    *   Downloads data only for business days.
    *   Stores the data in the `stock_market` database and the `market_data_close` collection.
