import pytest
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch
from database.delete_orphan_profiles import delete_orphan_profiles


@pytest.fixture
def mock_db_env():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_meta_profile (
            ticker TEXT PRIMARY KEY NOT NULL,
            company_name TEXT,
            type TEXT,
            sector TEXT,
            industry TEXT
        )
    """)
    # Insert test records
    cursor.executemany("""
        INSERT INTO ticker_meta_profile VALUES (?, ?, ?, ?, ?)
    """, [
        ('AAPL', 'Apple Inc.', 'EQUITY', 'Technology', 'Consumer Electronics'),
        ('MSFT', 'Microsoft Corp.', 'EQUITY', 'Technology', 'Software - Infrastructure'),
        ('FXE', 'Invesco CurrencyShares Euro Trust', 'ETF', 'Single Currency', 'Invesco'),
        ('OLDTICKER', 'Old Ticker Inc.', 'EQUITY', 'Financial', 'Banks'),
    ])
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    with patch('database.delete_orphan_profiles.get_sqlite_conn', _get_conn), \
         patch('database.delete_orphan_profiles.init_sqlite_db'):
        yield conn

    conn.close()


@patch('database.delete_orphan_profiles.get_all_tickers')
@patch('database.delete_orphan_profiles.clear_cache')
def test_delete_orphan_profiles_removes_non_csv_tickers(mock_clear_cache, mock_get_all_tickers, mock_db_env):
    # Only AAPL and MSFT exist in CSV files
    mock_get_all_tickers.return_value = ['AAPL', 'MSFT']

    deleted_count = delete_orphan_profiles()
    assert deleted_count == 2
    mock_clear_cache.assert_called_once()

    cursor = mock_db_env.cursor()
    cursor.execute("SELECT ticker FROM ticker_meta_profile ORDER BY ticker")
    remaining = [row[0] for row in cursor.fetchall()]

    assert remaining == ['AAPL', 'MSFT']
    assert 'FXE' not in remaining
    assert 'OLDTICKER' not in remaining


@patch('database.delete_orphan_profiles.get_all_tickers')
@patch('database.delete_orphan_profiles.clear_cache')
def test_delete_orphan_profiles_when_already_clean(mock_clear_cache, mock_get_all_tickers, mock_db_env):
    # All tickers in DB exist in CSV files
    mock_get_all_tickers.return_value = ['AAPL', 'MSFT', 'FXE', 'OLDTICKER']

    deleted_count = delete_orphan_profiles()
    assert deleted_count == 0
    mock_clear_cache.assert_not_called()

    cursor = mock_db_env.cursor()
    cursor.execute("SELECT COUNT(*) FROM ticker_meta_profile")
    count = cursor.fetchone()[0]
    assert count == 4
