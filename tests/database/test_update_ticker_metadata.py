import pytest
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from database.update_ticker_metadata import (
    get_unassigned_tickers,
    update_ticker_metadata
)


@pytest.fixture
def mock_db_env():
    # Set up in-memory SQLite database
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_close (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_meta_profile (
            ticker TEXT PRIMARY KEY NOT NULL,
            company_name TEXT,
            type TEXT,
            sector TEXT,
            industry TEXT
        )
    """)
    
    # AAPL is already assigned
    cursor.execute("INSERT INTO ticker_meta_profile VALUES ('AAPL', 'Apple Inc.', 'EQUITY', 'Technology', 'Consumer Electronics')")
    # AMZN is existing but marked as Unknown (tests that it is filtered out since it exists)
    cursor.execute("INSERT INTO ticker_meta_profile VALUES ('AMZN', 'Unknown', 'Unknown', 'Unknown', 'Unknown')")
    
    # MSFT is unassigned
    cursor.execute("INSERT INTO market_data_close VALUES ('2026-06-01', 'MSFT', 300.0)")
    
    # GOOG is unassigned
    cursor.execute("INSERT INTO fidelity_positions VALUES ('2026-06-01', 'GOOG', 10.0, 150.0, 1500.0, 1600.0, 'Stocks', 160.0, 100.0)")
    
    # AMZN is in fidelity_positions but already has an entry in ticker_meta_profile
    cursor.execute("INSERT INTO fidelity_positions VALUES ('2026-06-01', 'AMZN', 5.0, 100.0, 500.0, 550.0, 'Stocks', 110.0, 10.0)")
    
    # SPAXX** is cash and should be ignored
    cursor.execute("INSERT INTO fidelity_positions VALUES ('2026-06-01', 'SPAXX**', 1000.0, 1.0, 1000.0, 1000.0, 'Cash', 1.0, 10.0)")
    
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    with patch('database.update_ticker_metadata.get_sqlite_conn', _get_conn), \
         patch('database.update_ticker_metadata.init_sqlite_db'):
        yield conn
        
    conn.close()


def test_get_unassigned_tickers(mock_db_env):
    unassigned = get_unassigned_tickers()
    # AAPL is assigned. SPAXX** is cash.
    # MSFT and GOOG should be unassigned.
    assert unassigned == ['GOOG', 'MSFT']


@patch('yfinance.Ticker')
@patch('database.update_ticker_metadata.clear_cache')
def test_update_ticker_metadata_yfinance_success(mock_clear_cache, mock_ticker, mock_db_env):
    # Set up mocked yfinance info dictionaries for MSFT and GOOG
    mock_msft = MagicMock()
    mock_msft.get_info.return_value = {
        "longName": "Microsoft Corporation",
        "quoteType": "EQUITY",
        "sector": "Information Technology",
        "industry": "Software"
    }
    
    mock_goog = MagicMock()
    mock_goog.get_info.return_value = {
        "shortName": "Alphabet Inc.",
        "quoteType": "EQUITY",
        "sector": "Communication Services",
        "industry": "Interactive Media"
    }
    
    def side_effect(ticker_symbol):
        if ticker_symbol == "MSFT":
            return mock_msft
        elif ticker_symbol == "GOOG":
            return mock_goog
        return MagicMock()
        
    mock_ticker.side_effect = side_effect
    
    success = update_ticker_metadata(limit=10, delay=0.0)
    assert success is True
    
    # Verify values updated in the SQLite database
    cursor = mock_db_env.cursor()
    cursor.execute("SELECT ticker, company_name, type, sector, industry FROM ticker_meta_profile WHERE ticker IN ('GOOG', 'MSFT')")
    records = cursor.fetchall()
    assert len(records) == 2
    
    # GOOG verification
    goog_record = next(r for r in records if r[0] == 'GOOG')
    assert goog_record[1] == 'Alphabet Inc.'
    assert goog_record[2] == 'EQUITY'
    assert goog_record[3] == 'Communication Services'
    assert goog_record[4] == 'Interactive Media'
    
    # MSFT is remapped from 'Information Technology' to 'Technology'
    msft_record = next(r for r in records if r[0] == 'MSFT')
    assert msft_record[1] == 'Microsoft Corporation'
    assert msft_record[2] == 'EQUITY'
    assert msft_record[3] == 'Technology'
    assert msft_record[4] == 'Software'
    
    mock_clear_cache.assert_called_once()
