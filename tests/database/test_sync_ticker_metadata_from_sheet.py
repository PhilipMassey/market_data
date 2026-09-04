import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from database.sync_ticker_metadata_from_sheet import (
    normalize_sheet_url,
    parse_sheet_csv,
    sync_ticker_metadata_from_sheet,
    DEFAULT_SHEET_URL
)


def test_normalize_sheet_url():
    edit_url = "https://docs.google.com/spreadsheets/d/1m7e7jdBkC3H4EUqE9LF-ZwQIy5ru5cuC2WLzu3_Y89A/edit?usp=sharing"
    expected = "https://docs.google.com/spreadsheets/d/1m7e7jdBkC3H4EUqE9LF-ZwQIy5ru5cuC2WLzu3_Y89A/export?format=csv"
    assert normalize_sheet_url(edit_url) == expected

    # With gid parameter in edit URL
    edit_url_with_gid = "https://docs.google.com/spreadsheets/d/1m7e7jdBkC3H4EUqE9LF-ZwQIy5ru5cuC2WLzu3_Y89A/edit?gid=106245017#gid=106245017"
    expected_with_gid = "https://docs.google.com/spreadsheets/d/1m7e7jdBkC3H4EUqE9LF-ZwQIy5ru5cuC2WLzu3_Y89A/export?format=csv&gid=106245017"
    assert normalize_sheet_url(edit_url_with_gid) == expected_with_gid

    # Already export URL
    assert normalize_sheet_url(expected_with_gid) == expected_with_gid

    # Local file path
    assert normalize_sheet_url("/tmp/test.csv") == "/tmp/test.csv"


def test_parse_sheet_csv():
    sample_csv = """Ticker,Sector,Industry,OtherCol
AMDY,Derivative Income,YieldMax ETFs,123
MRNY,Derivative Income,YieldMax ETFs,456
AAPL,Technology,Consumer Electronics,789
SPAXX**,Cash,Cash,0
FCASH,Cash,Cash,0
,Empty,Row,0
VIXY,Trading--Miscellaneous,ProShares,999
"""
    records = parse_sheet_csv(sample_csv)
    assert len(records) == 4
    
    tickers = [r['ticker'] for r in records]
    assert tickers == ['AMDY', 'MRNY', 'AAPL', 'VIXY']
    
    amdy = next(r for r in records if r['ticker'] == 'AMDY')
    assert amdy['sector'] == 'Derivative Income'
    assert amdy['industry'] == 'YieldMax ETFs'


def test_sync_ticker_metadata_from_sheet():
    # Set up in-memory sqlite db
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE ticker_meta_profile (
            ticker TEXT PRIMARY KEY NOT NULL,
            company_name TEXT,
            type TEXT,
            sector TEXT,
            industry TEXT
        )
    """)
    # Insert existing rows:
    # AAPL with old metadata
    cursor.execute("INSERT INTO ticker_meta_profile VALUES ('AAPL', 'Apple Inc.', 'EQUITY', 'Old Sector', 'Old Industry')")
    # MSFT unaffected
    cursor.execute("INSERT INTO ticker_meta_profile VALUES ('MSFT', 'Microsoft', 'EQUITY', 'Technology', 'Software')")
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    sample_csv = """AMDY,Derivative Income,YieldMax ETFs
AAPL,Technology,Consumer Electronics
"""

    with patch('database.sync_ticker_metadata_from_sheet.get_sqlite_conn', _get_conn), \
         patch('database.sync_ticker_metadata_from_sheet.init_sqlite_db'), \
         patch('database.sync_ticker_metadata_from_sheet.fetch_csv_content', return_value=sample_csv), \
         patch('database.sync_ticker_metadata_from_sheet.clear_cache') as mock_clear_cache:

        result = sync_ticker_metadata_from_sheet("dummy_url")
        
        assert result['total'] == 2
        assert result['updated'] == 1 # AAPL updated
        assert result['inserted'] == 1 # AMDY inserted
        assert set(result['tickers']) == {'AAPL', 'AMDY'}
        mock_clear_cache.assert_called_once()

        # Verify DB state
        cursor.execute("SELECT ticker, sector, industry FROM ticker_meta_profile ORDER BY ticker")
        rows = cursor.fetchall()
        assert len(rows) == 3
        
        # AAPL updated
        assert rows[0] == ('AAPL', 'Technology', 'Consumer Electronics')
        # AMDY inserted
        assert rows[1] == ('AMDY', 'Derivative Income', 'YieldMax ETFs')
        # MSFT unchanged
        assert rows[2] == ('MSFT', 'Technology', 'Software')
