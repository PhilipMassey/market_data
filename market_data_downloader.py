import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def get_business_days(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """
    Returns a list of business days between two dates.
    """
    return pd.bdate_range(start=start_date, end=end_date)

def download_daily_close(tickers: List[str], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Downloads daily closing prices for a list of tickers and returns them as a list of documents.
    """
    data = yf.download(tickers, start=start_date, end=end_date, progress=False)
    
    if data.empty:
        return []

    close_prices = data['Close']
    
    documents = []
    for ticker in tickers:
        for date, price in close_prices[ticker].items():
            if pd.notna(price):
                documents.append({
                    "ticker": ticker,
                    "date": date.strftime('%Y-%m-%d'),
                    "close_price": price
                })
    return documents

def main():
    """
    Main function to download and store market data.
    """
    # 1. Initialize SQLite schema if not exists
    init_sqlite_db()

    # Example usage: Download data for the last 5 business days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10) # Go back a bit to ensure we get 5 business days
    
    business_days = get_business_days(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    if len(business_days) > 5:
        start_date = business_days[-6] # 5 days plus today
    else:
        start_date = business_days[0]

    tickers = ["AAPL", "GOOGL", "MSFT"] # Example tickers
    
    print(f"Downloading data for {tickers} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    data_to_insert = download_daily_close(tickers, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    if data_to_insert:
        rows_to_insert = [(d["date"], d["ticker"], float(d["close_price"])) for d in data_to_insert]
        
        try:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT INTO market_data_close (date, ticker, close_price)
                    VALUES (?, ?, ?)
                    ON CONFLICT(date, ticker) DO UPDATE SET close_price=excluded.close_price
                """, rows_to_insert)
            print(f"Successfully inserted/updated {len(rows_to_insert)} records in SQLite.")
        except Exception as e:
            print(f"An error occurred during insertion: {e}")

if __name__ == "__main__":
    main()
