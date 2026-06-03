import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database.schema_definitions import db_close
from utils.ticker_reader import get_all_tickers
from utils.calendar_utils import get_nyse_calendar_past_year

def find_missing_dates_in_db(tickers: List[str], expected_dates: List[str]) -> Dict[str, List[str]]:
    """
    Queries the database to find which dates are missing for each ticker.
    Returns a dictionary mapping tickers to a list of missing date strings.
    """
    missing_data = {}
    
    if not tickers or not expected_dates:
        return missing_data

    # MongoDB query to get existing dates for the tickers in our range
    pipeline = [
        {"$match": {
            "ticker": {"$in": tickers},
            "date": {"$in": expected_dates}
        }},
        {"$group": {
            "_id": "$ticker",
            "existing_dates": {"$push": "$date"}
        }}
    ]
    
    results = list(db_close.aggregate(pipeline))
    
    existing_lookup = {doc['_id']: set(doc['existing_dates']) for doc in results}
    expected_set = set(expected_dates)
    
    for ticker in tickers:
        existing_for_ticker = existing_lookup.get(ticker, set())
        missing_dates = expected_set - existing_for_ticker
        
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
    5. Inserts into DB.
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

    # 5. Transform and Insert
    documents_to_insert = []
    
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
                        documents_to_insert.append({
                            "ticker": ticker,
                            "date": missing_date,
                            "close_price": float(price)
                        })
            except KeyError:
                pass

    if documents_to_insert:
        print(f"Preparing to insert {len(documents_to_insert)} new records...")
        try:
            db_close.create_index([("ticker", 1), ("date", 1)], unique=True)
            result = db_close.insert_many(documents_to_insert, ordered=False)
            print(f"Successfully inserted {len(result.inserted_ids)} records.")
        except Exception as e:
            print(f"Insertion completed with some exceptions (likely duplicates ignored): {e}")
    else:
         print("No valid price data found to insert for the missing dates.")


if __name__ == "__main__":
    download_and_insert_missing_close_prices()
