import os
import sqlite3
from contextlib import contextmanager

SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH', '/Users/philipmassey/projects/.data/market_data.db')

@contextmanager
def get_sqlite_conn():
    """
    Context manager for SQLite connection.
    Automatically commits and closes the connection.
    """
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_sqlite_db():
    """
    Initializes the SQLite database schema if it doesn't exist.
    """
    # Create the parent directory if it doesn't exist
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        # Create market_data_close table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data_close (
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                close_price REAL NOT NULL,
                PRIMARY KEY (date, ticker)
            )
        """)
        # Create index on ticker for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_close_ticker ON market_data_close (ticker)
        """)
