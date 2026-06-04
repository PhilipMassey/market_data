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

    # Build query with placeholders
    placeholders_tickers = ', '.join(['?'] * len(tickers))
    placeholders_dates = ', '.join(['?'] * len(expected_dates))
    
    query = f"""
        SELECT date, ticker 
        FROM market_data_close 
        WHERE ticker IN ({placeholders_tickers}) AND date IN ({placeholders_dates})
    """
    
    params = list(tickers) + list(expected_dates)
    
    # Track existing dates per ticker
    existing_dates_map = {ticker: set() for ticker in tickers}
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        for row in cursor.fetchall():
            d_str, ticker = row
            if ticker in existing_dates_map:
                existing_dates_map[ticker].add(d_str)
                
    # Determine the missing dates
    expected_set = set(expected_dates)
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
    5. Downloads missing data via yfinance.
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

    # 3. Tickers - Now using the master function
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

    all_missing_dates = [date for dates in missing_data_map.values() for date in dates]
    if not all_missing_dates:
        print("No specific dates are missing. Exiting.")
        return

    min_fetch_date = min(all_missing_dates)
    max_fetch_date_obj = datetime.strptime(max(all_missing_dates), '%Y-%m-%d') + timedelta(days=1)
    max_fetch_date = max_fetch_date_obj.strftime('%Y-%m-%d')

    print(f"Fetching data from yfinance between {min_fetch_date} and {max_fetch_date}...")

    # 5. Download Data
    try:
        data = yf.download(tickers_with_missing_data, start=min_fetch_date, end=max_fetch_date, progress=False)
    except Exception as e:
        print(f"Error fetching from yfinance: {e}")
        return

    if data.empty:
        print("yfinance returned no data.")
        return

    close_prices = data['Close']
    
    if len(tickers_with_missing_data) == 1:
        close_prices = close_prices.to_frame(name=tickers_with_missing_data[0])

    # 6. Transform and Bulk Upsert in SQLite
    rows_to_insert = []
    
    for ticker, missing_dates in missing_data_map.items():
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


if __name__ == "__main__":
    download_and_insert_missing_close_prices()
