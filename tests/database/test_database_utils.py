import pytest
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch
from database.database_utils import get_close_price_records

@pytest.fixture
def mock_sqlite_conn():
    """
    Fixture that creates an in-memory SQLite database and patches get_sqlite_conn.
    """
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE market_data_close (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()
    
    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()
        
    with patch('database.database_utils.get_sqlite_conn', _get_conn):
        yield conn
        
    conn.close()

def test_get_close_price_records_empty_inputs(mock_sqlite_conn):
    """
    Test get_close_price_records with empty tickers or dates.
    """
    assert get_close_price_records([], []) == []
    assert get_close_price_records(["AAPL"], []) == []
    assert get_close_price_records([], ["2026-05-19"]) == []

def test_get_close_price_records_matching_query(mock_sqlite_conn):
    """
    Test that get_close_price_records queries matching normalized rows in SQLite
    and returns them in wide format.
    """
    # 1. Populate the in-memory SQLite database
    cursor = mock_sqlite_conn.cursor()
    cursor.executemany("""
        INSERT INTO market_data_close (date, ticker, close_price)
        VALUES (?, ?, ?)
    """, [
        ("2026-05-19", "AAPL", 150.0),
        ("2026-05-19", "MSFT", 300.0),
        ("2026-05-19", "GOOGL", 170.0),
        ("2026-05-20", "AAPL", 152.0),
        ("2026-05-20", "MSFT", 302.0),
        ("2026-05-21", "AAPL", 153.0)
    ])
    mock_sqlite_conn.commit()

    # 2. Query for AAPL and MSFT on 2026-05-19 and 2026-05-20
    tickers = ["AAPL", "MSFT"]
    dates = ["2026-05-19", "2026-05-20"]
    
    records = get_close_price_records(tickers, dates)
    
    # 3. Assert correct wide-format matching and sorting
    assert len(records) == 2
    
    assert records[0] == {"Date": "2026-05-19", "AAPL": 150.0, "MSFT": 300.0}
    assert records[1] == {"Date": "2026-05-20", "AAPL": 152.0, "MSFT": 302.0}
