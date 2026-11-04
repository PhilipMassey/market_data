from typing import List, Dict, Any
from database.sqlite_connection import get_sqlite_conn

def get_close_price_records(ltickers: List[str], dates: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieves close price records matching the given tickers and dates from the SQLite database.
    
    Transforms the SQLite normalized rows (date, ticker, price) back into the wide format
    expected by downstream components:
    [
        {
            "Date": "2023-01-25",
            "AAPL": 141.86,
            "MSFT": 240.61
        },
        ...
    ]
    
    Args:
        ltickers: List of ticker symbols (strings)
        dates: List of dates (strings in YYYY-MM-DD format)
        
    Returns:
        List of dictionaries containing 'Date' and close prices for the requested tickers.
    """
    if not ltickers or not dates:
        return []
        
    # Build query with placeholders
    placeholders_tickers = ', '.join(['?'] * len(ltickers))
    placeholders_dates = ', '.join(['?'] * len(dates))
    
    query = f"""
        SELECT date, ticker, close_price 
        FROM market_data_close 
        WHERE ticker IN ({placeholders_tickers}) AND date IN ({placeholders_dates})
    """
    
    params = list(ltickers) + list(dates)
    
    results_by_date = {} # date -> {ticker: price}
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        for row in cursor.fetchall():
            d_str, ticker, price = row
            if d_str not in results_by_date:
                results_by_date[d_str] = {"Date": d_str}
            results_by_date[d_str][ticker] = price
            
    # Return as list of wide dictionaries, sorted by Date chronologically
    return sorted(list(results_by_date.values()), key=lambda x: x["Date"])


def get_latest_price(symbol: str, conn_fn=None) -> float:
    """Returns the most recent close price for `symbol` from `market_data_close`."""
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close_price 
            FROM market_data_close 
            WHERE ticker = ? 
            ORDER BY date DESC LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
    return None


def get_price_at_date(symbol: str, date_str: str, conn_fn=None) -> float:
    """Returns the latest close price for `symbol` on or before `date_str`."""
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close_price 
            FROM market_data_close 
            WHERE ticker = ? AND date <= ? 
            ORDER BY date DESC LIMIT 1
        """, (symbol, date_str))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
    return None


def get_latest_snapshot_date_on_or_before(date_str: str, conn_fn=None) -> str:
    """Returns the latest `fidelity_positions` snapshot date on or before `date_str`, falling back to MIN(date)."""
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(date) 
            FROM fidelity_positions 
            WHERE date <= ?
        """, (date_str,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

        cursor.execute("SELECT MIN(date) FROM fidelity_positions")
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

    return date_str

