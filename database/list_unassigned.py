import os
import sys
import sqlite3

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def list_dud_tickers():
    """
    Queries and lists all tickers from historical data or positions
    that are either missing from ticker_meta_profile or marked as 'Unknown'.
    """
    init_sqlite_db()
    
    query = """
        SELECT DISTINCT t.ticker, 
               CASE 
                   WHEN m.ticker IS NULL THEN 'Missing'
                   ELSE 'Unknown'
               END as status
        FROM (
            SELECT DISTINCT ticker FROM market_data_close
            UNION
            SELECT DISTINCT symbol AS ticker FROM fidelity_positions
        ) t
        LEFT JOIN ticker_meta_profile m ON t.ticker = m.ticker
        WHERE m.ticker IS NULL 
           OR m.sector IS NULL 
           OR m.sector = 'Unknown'
           OR m.industry IS NULL 
           OR m.industry = 'Unknown'
        ORDER BY t.ticker
    """
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
    # Filter out cash designations
    ignored_symbols = {
        'FDIC-INSURED DEPOSIT SWEEP', 'PENDING ACTIVITY', 'FCASH', 'CASH', 'PENDING'
    }
    
    dud_tickers = [
        row for row in rows 
        if row[0] and not row[0].endswith('**') and row[0] not in ignored_symbols
    ]
    
    print(f"Found {len(dud_tickers)} dud (unassigned or 'Unknown') tickers in database:\n")
    print(f"{'Ticker':<10} | {'Status':<10}")
    print("-" * 25)
    
    for ticker, status in dud_tickers:
        print(f"{ticker:<10} | {status:<10}")
        
    return dud_tickers

if __name__ == "__main__":
    list_dud_tickers()
