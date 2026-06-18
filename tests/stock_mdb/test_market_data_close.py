import pytest
import pandas as pd
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from unittest.mock import patch
from stock_mdb.market_data_close import (
    find_missing_dates_in_db,
    download_and_insert_missing_close_prices
)

class MockYFData:
    def __init__(self, close_df):
        self.close_df = close_df
    
    @property
    def empty(self):
        return self.close_df.empty
    
    def __getitem__(self, key):
        if key == 'Close':
            return self.close_df
        raise KeyError(key)

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
        
    with patch('stock_mdb.market_data_close.get_sqlite_conn', _get_conn):
        yield conn
        
    conn.close()

def test_find_missing_dates_empty_inputs(mock_sqlite_conn):
    """
    Test find_missing_dates_in_db with empty input parameters.
    """
    assert find_missing_dates_in_db([], []) == {}
    assert find_missing_dates_in_db(["AAPL"], []) == {}
    assert find_missing_dates_in_db([], ["2026-05-19"]) == {}

def test_find_missing_dates_all_missing(mock_sqlite_conn):
    """
    Test when no records exist in the database, meaning all dates are missing.
    """
    tickers = ["AAPL", "MSFT"]
    expected_dates = ["2026-05-19", "2026-05-20"]
    missing = find_missing_dates_in_db(tickers, expected_dates)
    
    assert missing == {
        "AAPL": ["2026-05-19", "2026-05-20"],
        "MSFT": ["2026-05-19", "2026-05-20"]
    }

def test_find_missing_dates_some_existing(mock_sqlite_conn):
    """
    Test when some records already exist in the database.
    """
    cursor = mock_sqlite_conn.cursor()
    cursor.executemany("""
        INSERT INTO market_data_close (date, ticker, close_price)
        VALUES (?, ?, ?)
    """, [
        ("2026-05-19", "AAPL", 150.0),
        ("2026-05-20", "MSFT", 300.0)
    ])
    mock_sqlite_conn.commit()
    
    tickers = ["AAPL", "MSFT"]
    expected_dates = ["2026-05-19", "2026-05-20"]
    missing = find_missing_dates_in_db(tickers, expected_dates)
    
    assert missing == {
        "AAPL": ["2026-05-20"],
        "MSFT": ["2026-05-19"]
    }

def test_find_missing_dates_none_missing(mock_sqlite_conn):
    """
    Test when all expected records already exist in the database.
    """
    cursor = mock_sqlite_conn.cursor()
    cursor.executemany("""
        INSERT INTO market_data_close (date, ticker, close_price)
        VALUES (?, ?, ?)
    """, [
        ("2026-05-19", "AAPL", 150.0),
        ("2026-05-19", "MSFT", 299.0),
        ("2026-05-20", "AAPL", 151.0),
        ("2026-05-20", "MSFT", 300.0)
    ])
    mock_sqlite_conn.commit()
    
    tickers = ["AAPL", "MSFT"]
    expected_dates = ["2026-05-19", "2026-05-20"]
    missing = find_missing_dates_in_db(tickers, expected_dates)
    
    assert missing == {}

@patch('stock_mdb.market_data_close.get_nyse_calendar_past_year')
@patch('stock_mdb.market_data_close.get_all_tickers')
@patch('yfinance.download')
def test_download_and_insert_missing_close_prices_success(
    mock_yf_download,
    mock_get_all_tickers,
    mock_get_calendar,
    mock_sqlite_conn
):
    """
    Test the full workflow when missing data needs to be downloaded and upserted in SQLite.
    """
    # 1. Setup mock calendar and tickers
    mock_get_calendar.return_value = ["2026-05-19", "2026-05-20"]
    mock_get_all_tickers.return_value = ["AAPL", "MSFT"]
    
    # 2. Setup mock yfinance return value
    # Only AAPL and MSFT will have missing dates (since DB is initially empty)
    close_df = pd.DataFrame(
        {
            "AAPL": [150.0, 152.0],
            "MSFT": [300.0, 305.0]
        },
        index=pd.to_datetime(["2026-05-19", "2026-05-20"])
    )
    def download_side_effect(tickers, start, end, progress=False):
        ticker = tickers[0]
        return MockYFData(close_df[[ticker]])
    mock_yf_download.side_effect = download_side_effect
    
    # 3. Call the target function
    download_and_insert_missing_close_prices()
    
    # 4. Verify mock calls
    mock_get_calendar.assert_called_once()
    mock_get_all_tickers.assert_called_once()
    
    from unittest.mock import call
    mock_yf_download.assert_has_calls([
        call(["AAPL"], start="2026-05-19", end="2026-05-21", progress=False),
        call(["MSFT"], start="2026-05-19", end="2026-05-21", progress=False)
    ], any_order=True)
    
    # 5. Verify records were inserted in SQLite DB
    cursor = mock_sqlite_conn.cursor()
    cursor.execute("SELECT date, ticker, close_price FROM market_data_close")
    inserted = cursor.fetchall()
    
    assert len(inserted) == 4
    
    assert ("2026-05-19", "AAPL", 150.0) in inserted
    assert ("2026-05-20", "AAPL", 152.0) in inserted
    assert ("2026-05-19", "MSFT", 300.0) in inserted
    assert ("2026-05-20", "MSFT", 305.0) in inserted

@patch('stock_mdb.market_data_close.get_nyse_calendar_past_year')
@patch('stock_mdb.market_data_close.get_all_tickers')
@patch('yfinance.download')
def test_download_and_insert_missing_close_prices_no_missing(
    mock_yf_download,
    mock_get_all_tickers,
    mock_get_calendar,
    mock_sqlite_conn
):
    """
    Test that no download or insertion occurs if the database is already fully populated.
    """
    # 1. Setup mock calendar and tickers
    mock_get_calendar.return_value = ["2026-05-19"]
    mock_get_all_tickers.return_value = ["AAPL"]
    
    # 2. Populate the DB with the expected data
    cursor = mock_sqlite_conn.cursor()
    cursor.execute("INSERT INTO market_data_close (date, ticker, close_price) VALUES ('2026-05-19', 'AAPL', 150.0)")
    mock_sqlite_conn.commit()
    
    # 3. Call the function
    download_and_insert_missing_close_prices()
    
    # 4. Verify yfinance was not called
    mock_yf_download.assert_not_called()
    
    # 5. Verify DB contents remain identical
    cursor.execute("SELECT date, ticker, close_price FROM market_data_close")
    inserted = cursor.fetchall()
    assert inserted == [("2026-05-19", "AAPL", 150.0)]
