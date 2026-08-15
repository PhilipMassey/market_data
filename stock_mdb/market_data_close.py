import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from utils.ticker_reader import get_all_tickers
from utils.calendar_utils import get_nyse_calendar_past_year

def find_missing_dates_in_db(tickers: List[str], expected_dates: List[str]) -> Dict[str, List[str]]:
    """
    Queries the SQLite database to find which dates are missing for each ticker.
    Returns a dictionary mapping tickers to a list of missing date strings.
    """
    missing_data = {}
    
    if not tickers or not expected_dates:
        return missing_data

    min_date = min(expected_dates)
    max_date = max(expected_dates)
    expected_set = set(expected_dates)
    existing_dates_map = {ticker: set() for ticker in tickers}
    
    # Query in ticker chunks of 500 to optimize SQLite query parsing and stay well within parameter limits
    chunk_size = 500
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        for i in range(0, len(tickers), chunk_size):
            ticker_chunk = tickers[i:i + chunk_size]
            placeholders = ', '.join(['?'] * len(ticker_chunk))
            query = f"""
                SELECT date, ticker 
                FROM market_data_close 
                WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
            """
            params = ticker_chunk + [min_date, max_date]
            cursor.execute(query, params)
            for row in cursor.fetchall():
                d_str, ticker = row
                if ticker in existing_dates_map and d_str in expected_set:
                    existing_dates_map[ticker].add(d_str)
                
    # Determine the missing dates
    for ticker in tickers:
        existing_set = existing_dates_map[ticker]
        missing_dates = expected_set - existing_set
        if missing_dates:
            missing_data[ticker] = sorted(list(missing_dates))
            
    return missing_data

def download_and_insert_missing_close_prices():
    """
    Main daily maintenance procedure:
    1. Initializes SQLite schema.
    2. Gets past year's calendar.
    3. Gets all target tickers.
    4. Finds missing dates in DB.
    5. Downloads missing data via yfinance in batches (grouped by missing date range).
    6. Inserts/updates in SQLite DB.
    """
    print("Starting daily SQLite market_data_close maintenance...")
    
    # 1. Initialize DB schema
    init_sqlite_db()
    
    # 2. Calendar
    expected_dates = get_nyse_calendar_past_year()
    if not expected_dates:
        print("No expected dates found.")
        return
    print(f"Targeting {len(expected_dates)} trading days between {expected_dates[0]} and {expected_dates[-1]}")

    # 3. Tickers - Master function
    tickers = get_all_tickers()
    if not tickers:
        print("No tickers found from any source. Exiting.")
        return
    print(f"Found {len(tickers)} unique tickers from all sources.")

    # 4. Missing Data Delta
    missing_data_map = find_missing_dates_in_db(tickers, expected_dates)
    
    if not missing_data_map:
        print("Database is completely up to date. No missing records found.")
        return
    
    tickers_with_missing_data = list(missing_data_map.keys())
    print(f"Found missing data for {len(tickers_with_missing_data)} tickers.")

    rows_to_insert = []
    
    # 5. Group missing tickers by date range to minimize yfinance API load via batch requests
    range_groups: Dict[tuple, List[tuple]] = {}
    for ticker, missing_dates in missing_data_map.items():
        if not missing_dates:
            continue
        ticker_min = min(missing_dates)
        ticker_max_obj = datetime.strptime(max(missing_dates), '%Y-%m-%d') + timedelta(days=1)
        ticker_max = ticker_max_obj.strftime('%Y-%m-%d')
        key = (ticker_min, ticker_max)
        if key not in range_groups:
            range_groups[key] = []
        range_groups[key].append((ticker, missing_dates))

    BATCH_SIZE = 50

    for (start_date, end_date), item_list in range_groups.items():
        for i in range(0, len(item_list), BATCH_SIZE):
            batch_items = item_list[i:i + BATCH_SIZE]
            batch_tickers = [item[0] for item in batch_items]
            
            print(f"Fetching data for batch of {len(batch_tickers)} ticker(s) from yfinance between {start_date} and {end_date}...")
            
            try:
                data = yf.download(batch_tickers, start=start_date, end=end_date, progress=False)
                if data.empty:
                    continue
                    
                try:
                    close_prices = data['Close']
                except (KeyError, TypeError, AttributeError):
                    close_prices = data

                if isinstance(close_prices, pd.Series):
                    close_prices = close_prices.to_frame(name=batch_tickers[0])
                elif isinstance(close_prices, pd.DataFrame):
                    if isinstance(close_prices.columns, pd.MultiIndex):
                        close_prices.columns = close_prices.columns.get_level_values(-1)
                    if len(batch_tickers) == 1 and batch_tickers[0] not in close_prices.columns and len(close_prices.columns) > 0:
                        close_prices = close_prices.rename(columns={close_prices.columns[0]: batch_tickers[0]})
                
                for ticker, missing_dates in batch_items:
                    if ticker not in close_prices.columns:
                        continue
                    ticker_series = close_prices[ticker]
                    for missing_date in missing_dates:
                        try:
                            date_ts = pd.Timestamp(missing_date)
                            if date_ts in ticker_series.index:
                                price = ticker_series[date_ts]
                                import math
                                if pd.notna(price) and not math.isnan(price):
                                    rows_to_insert.append((missing_date, ticker, float(price)))
                        except KeyError:
                            pass
            except Exception as e:
                print(f"Error fetching batch data for {batch_tickers}: {e}")

    if rows_to_insert:
        print(f"Preparing to insert/update {len(rows_to_insert)} records in SQLite...")
        try:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT INTO market_data_close (date, ticker, close_price)
                    VALUES (?, ?, ?)
                    ON CONFLICT(date, ticker) DO UPDATE SET close_price=excluded.close_price
                """, rows_to_insert)
            print(f"Successfully updated/inserted {len(rows_to_insert)} records in SQLite.")
        except Exception as e:
            print(f"Insertion completed with some exceptions: {e}")
    else:
         print("No valid price data found to insert for the missing dates.")


