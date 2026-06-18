import os
import sqlite3
from contextlib import contextmanager

# Fallback to local workspace database if it exists
_dir = os.path.dirname(os.path.abspath(__file__))
_local_db = os.path.join(_dir, 'market_data.db')
SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH')
if not SQLITE_DB_PATH:
    if os.path.exists(_local_db):
        SQLITE_DB_PATH = _local_db
    else:
        SQLITE_DB_PATH = '/Users/philipmassey/projects/.data/market_data.db'

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
        # Create fidelity_positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fidelity_positions (
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL,
                average_cost_basis REAL,
                cost_basis_total REAL,
                current_value REAL,
                account_name TEXT,
                last_price REAL,
                percent_of_account REAL,
                PRIMARY KEY (date, symbol)
            )
        """)
        # Create indexes on fidelity_positions for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fidelity_positions_symbol ON fidelity_positions (symbol)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fidelity_positions_date ON fidelity_positions (date)
        """)
