import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database import get_db_connection, get_database, get_close_price_collection, insert_close_prices

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
    client = get_db_connection()
    db = get_database(client)
    collection = get_close_price_collection(db)

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
        # To prevent duplicates, you should create a unique index in MongoDB
        # db.market_data_close.createIndex({ ticker: 1, date: 1 }, { unique: true })
        try:
            insert_close_prices(collection, data_to_insert)
            print(f"Successfully inserted {len(data_to_insert)} documents.")
        except Exception as e:
            print(f"An error occurred during insertion: {e}")
            print("Consider creating a unique index to handle duplicates gracefully.")

    client.close()

if __name__ == "__main__":
    main()
