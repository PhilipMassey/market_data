import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pymongo import UpdateOne
from database.schema_definitions import db_close
from utils.ticker_reader import get_all_tickers
from utils.calendar_utils import get_nyse_calendar_past_year

def find_missing_dates_in_db(tickers: List[str], expected_dates: List[str]) -> Dict[str, List[str]]:
    """
    Queries the database to find which dates are missing for each ticker.
    Returns a dictionary mapping tickers to a list of missing date strings.
    
    The database uses a wide schema:
    {
        "Date": datetime.datetime(2023, 1, 25, 0, 0),
        "AAPL": 141.86,
        "MSFT": 240.61,
        ...
    }
    """
    missing_data = {}
    
    if not tickers or not expected_dates:
        return missing_data

    # Convert string dates to datetime objects (at midnight) as stored in MongoDB
    expected_datetimes = []
    date_str_to_dt = {}
    for d_str in expected_dates:
        try:
            dt = datetime.strptime(d_str, '%Y-%m-%d')
            expected_datetimes.append(dt)
            date_str_to_dt[dt] = d_str
        except ValueError:
            pass

    if not expected_datetimes:
        return missing_data

    # Query the database for existing records on these dates
    query = {"Date": {"$in": expected_datetimes}}
    
    # Project only Date and the requested tickers
    projection = {"_id": 0, "Date": 1}
    for ticker in tickers:
        projection[ticker] = 1
        
    results = list(db_close.find(query, projection))
    
    # Build a lookup of existing dates per ticker
    existing_dates_map = {ticker: set() for ticker in tickers}
    for doc in results:
        dt_val = doc.get("Date")
        if not isinstance(dt_val, datetime):
            continue
        d_str = date_str_to_dt.get(dt_val)
        if not d_str:
            continue
            
        for ticker in tickers:
            # Check if ticker has a non-null price in this document
            if ticker in doc and doc[ticker] is not None and pd.notna(doc[ticker]):
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
    1. Gets past year's calendar.
    2. Gets all target tickers.
    3. Finds missing dates in DB.
    4. Downloads missing data via yfinance.
    5. Inserts/updates in DB.
    """
    print("Starting daily db_close maintenance...")
    
    # 1. Calendar
    expected_dates = get_nyse_calendar_past_year()
    if not expected_dates:
        print("No expected dates found.")
        return
    print(f"Targeting {len(expected_dates)} trading days between {expected_dates[0]} and {expected_dates[-1]}")

    # 2. Tickers - Now using the master function
    tickers = get_all_tickers()
    if not tickers:
        print("No tickers found from any source. Exiting.")
        return
    print(f"Found {len(tickers)} unique tickers from all sources.")

    # 3. Missing Data Delta
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

    # 4. Download Data
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

    # 5. Transform and Bulk Upsert
    updates_by_date = {} # datetime -> {ticker: price}
    
    for ticker, missing_dates in missing_data_map.items():
        if ticker not in close_prices.columns:
            continue
            
        ticker_series = close_prices[ticker]
        
        for missing_date in missing_dates:
            try:
                date_ts = pd.Timestamp(missing_date)
                if date_ts in ticker_series.index:
                    price = ticker_series[date_ts]
                    if pd.notna(price):
                        dt_val = datetime.strptime(missing_date, '%Y-%m-%d')
                        if dt_val not in updates_by_date:
                            updates_by_date[dt_val] = {}
                        updates_by_date[dt_val][ticker] = float(price)
            except KeyError:
                pass

    if updates_by_date:
        print(f"Preparing to update {len(updates_by_date)} daily records in DB...")
        try:
            # Ensure index on Date is unique
            db_close.create_index("Date", unique=True)
            
            for dt_val, ticker_prices in updates_by_date.items():
                db_close.update_one(
                    {"Date": dt_val},
                    {"$set": ticker_prices},
                    upsert=True
                )
            print(f"Successfully updated {len(updates_by_date)} daily records in DB.")
        except Exception as e:
            print(f"Insertion completed with some exceptions: {e}")
    else:
         print("No valid price data found to insert for the missing dates.")


if __name__ == "__main__":
    download_and_insert_missing_close_prices()
