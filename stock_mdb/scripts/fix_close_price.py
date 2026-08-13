from utils.ticker_reader import get_all_tickers
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from database.sqlite_connection import get_sqlite_conn

def get_db_prices(ticker):
    """Retrieve all date/price records for TICKER from the local SQLite database"""
    query = """
        SELECT date, close_price 
        FROM market_data_close 
        WHERE ticker = ? 
        ORDER BY date ASC
    """
    records = []
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (ticker,))
        for row in cursor.fetchall():
            records.append({
                "date": row[0],
                "price": float(row[1])
            })
    start_date = 0
    end_date = 0
    if len(records)> 2:
        start_date = records[0]['date']
        end_date = records[-1]['date']

    return start_date, end_date, records


def get_mismatches_for_period(ticker, start_date, end_date, db_records, tolerance=0.5):
    """
    Returns a list of dictionary mismatches between SQLite DB and yfinance for a given year.
    """
    db_map = {r["date"]: r["price"] for r in db_records}

    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if data.empty:
        return []

    # Handle both Series and MultiIndex DataFrame structures from yfinance
    close_prices = data['Close']
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]
        
    yf_map = {
        ts.strftime("%Y-%m-%d"): float(val) 
        for ts, val in close_prices.items() if pd.notna(val)
    }

    # 4. Compare and collect discrepancies
    discrepancies = []
    for date_str, db_price in db_map.items():
        if date_str in yf_map:
            yf_price = yf_map[date_str]
            diff = abs(db_price - yf_price)
            
            if diff > tolerance:
                discrepancies.append({
                    "date": date_str,
                    "db_price": round(db_price, 0),
                    "yf_price": round(yf_price, 0),
                    "diff": round(diff, 4)
                })

    return discrepancies


def update_db_with_yf_prices(ticker, mismatches):
    if not mismatches:
        print("No mismatches to update.")
        return

    # 1. Prepare a list of tuples containing (new_price, ticker, date)
    # This matches the order of the ? placeholders in the SQL query
    update_data = [
        (m['yf_price'], ticker, m['date']) 
        for m in mismatches
    ]

    # 2. Define the UPDATE query
    update_query = """
        UPDATE market_data_close
        SET close_price = ?
        WHERE ticker = ? AND date = ?
    """

    # 3. Execute the bulk update and commit the changes
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.executemany(update_query, update_data)
        conn.commit()  # Crucial: save the changes to the database
        
        print(f"Successfully updated {cursor.rowcount} rows for {ticker}.")

if __name__ == "__main__":
    tickers = get_all_tickers()
    for ticker in tickers:
        start_date, end_date, db_records = get_db_prices(ticker)
        mismatches = get_mismatches_for_period(ticker,start_date, end_date, db_records)
        print(f'Number of mismatches for {ticker}: {len(mismatches)}')
        update_db_with_yf_prices(ticker, mismatches)