import os
import sys
import time
import yfinance as yf

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from portfolio.ticker_period_ranks_data import clear_cache


def get_unassigned_tickers():
    """
    Identifies tickers from portfolio positions or historical close prices
    that lack sector or industry profile metadata in SQLite.
    """
    init_sqlite_db()
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch unique tickers from historical close prices
        cursor.execute("SELECT DISTINCT ticker FROM market_data_close")
        db_tickers = {row[0].upper() for row in cursor.fetchall() if row[0]}
        
        # 2. Fetch unique symbols from Fidelity positions
        cursor.execute("SELECT DISTINCT symbol FROM fidelity_positions")
        fid_tickers = {row[0].upper() for row in cursor.fetchall() if row[0]}
        
        # Combine sets
        all_tickers = db_tickers.union(fid_tickers)
        
        # Filter out cash designations
        ignored_symbols = {
            'FDIC-INSURED DEPOSIT SWEEP', 'PENDING ACTIVITY', 'FCASH', 'CASH', 'PENDING'
        }
        all_tickers = {
            t for t in all_tickers 
            if t and not t.endswith('**') and t not in ignored_symbols
        }
        
        # 3. Find tickers that already exist in ticker_meta_profile
        cursor.execute("SELECT ticker FROM ticker_meta_profile")
        existing_tickers = {row[0].upper() for row in cursor.fetchall()}
        
        # Return sorted list of new (unseen) tickers
        return sorted(list(all_tickers - existing_tickers))


import contextlib
import io
import logging

# Suppress yfinance internal logger messages
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

@contextlib.contextmanager
def silence_outputs():
    """Context manager to suppress stdout and stderr."""
    new_target = io.StringIO()
    with contextlib.redirect_stdout(new_target), contextlib.redirect_stderr(new_target):
        yield


def update_ticker_metadata(delay=0.2):
    """
    Identifies unassigned tickers, fetches their metadata from Yahoo Finance using yfinance,
    saves the 5-column metadata to SQLite, and invalidates rankings cache.
    """
    init_sqlite_db()
    
    unassigned = get_unassigned_tickers()
    if not unassigned:
        print("No unassigned tickers found. Database is fully up-to-date!")
        return True
        
    print(f"Unassigned tickers are {', '.join(unassigned)}")
    
    inserted_records = []
    no_metadata_tickers = []
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        
        for idx, ticker in enumerate(unassigned):
            company_name = "Unknown"
            quote_type = "Unknown"
            sector = "Unknown"
            industry = "Unknown"
            
            # Silence all stdout/stderr from yfinance library
            with silence_outputs():
                try:
                    stock_data = yf.Ticker(ticker)
                    info = stock_data.get_info()
                    if isinstance(info, dict):
                        company_name = info.get("longName", info.get("shortName", "Unknown"))
                        quote_type = info.get("quoteType", "Unknown")
                        sector = info.get("sector", info.get("category", "Unknown"))
                        industry = info.get("industry", info.get("fundFamily", "Unknown"))
                except Exception:
                    pass
            
            # Remap IT sector names for internal consistency
            if sector == "Information Technology":
                sector = "Technology"
                
            cursor.execute("""
                INSERT OR IGNORE INTO ticker_meta_profile (ticker, company_name, type, sector, industry)
                VALUES (?, ?, ?, ?, ?)
            """, (ticker, company_name, quote_type, sector, industry))
            
            # If it could not retrieve any meaningful fields (all default to Unknown), classify as No Metadata
            if company_name == "Unknown" and sector == "Unknown" and industry == "Unknown":
                no_metadata_tickers.append(ticker)
            else:
                inserted_records.append(
                    f"  {ticker} - Name='{company_name}' | Type={quote_type} | Sector={sector} | Industry={industry}"
                )
                
            # Prevent hitting Yahoo Finance rate limits
            if idx < len(unassigned) - 1:
                time.sleep(delay)
                
    # Print results in required format
    print("Inserted tickers meta data")
    print(f"No meta data tickers are {', '.join(no_metadata_tickers)}")
    
    if len(inserted_records) > 0:
        clear_cache()
        
    return True


if __name__ == "__main__":
    update_ticker_metadata()
