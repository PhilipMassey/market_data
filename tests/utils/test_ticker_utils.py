import os
import sqlite3
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from utils.ticker_utils import (
    portfolio_from_file,
    get_dir_port_tickers,
    get_port_and_tickers,
    get_tickers,
    get_tickers_dir_or_port,
    get_tickers_for_portfolios,
    get_portfolio_dirs,
    df_ticker_profile,
    all as ALL_DIRS,
)


@pytest.fixture
def mock_portfolio_structure(tmp_path):
    sub_dir = tmp_path / "Tech"
    sub_dir.mkdir()
    csv_file = sub_dir / "growth.csv"
    csv_file.write_text("Symbol,Weight\nAAPL,0.6\nMSFT,0.4\n")
    return tmp_path


def test_portfolio_from_file(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        df = portfolio_from_file("Tech", "growth.csv")
        assert not df.empty
        assert 'portfolio' in df.columns
        assert df['portfolio'].iloc[0] == 'growth'
        assert list(df['ticker']) == ['AAPL', 'MSFT']


def test_get_dir_port_tickers(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        df = get_dir_port_tickers("Tech")
        assert len(df) == 2
        assert set(df['ticker']) == {'AAPL', 'MSFT'}


def test_get_port_and_tickers(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        df_all = get_port_and_tickers("Tech")
        assert len(df_all) == 2

        df_all_dirs = get_port_and_tickers(ALL_DIRS)
        assert len(df_all_dirs) == 2


def test_get_tickers(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        tickers = get_tickers(directory="Tech")
        assert set(tickers) == {'AAPL', 'MSFT'}

        tickers_port = get_tickers(ports=['growth'])
        assert set(tickers_port) == {'AAPL', 'MSFT'}


def test_get_tickers_dir_or_port(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        tickers = get_tickers_dir_or_port(directory="Tech", port=None)
        assert set(tickers) == {'AAPL', 'MSFT'}

        tickers_port = get_tickers_dir_or_port(directory=None, port='growth')
        assert set(tickers_port) == {'AAPL', 'MSFT'}

        empty = get_tickers_dir_or_port(directory=None, port=None)
        assert empty == []


def test_get_portfolio_dirs(mock_portfolio_structure):
    with patch('utils.ticker_utils.data_dir', str(mock_portfolio_structure)):
        dirs = get_portfolio_dirs()
        assert dirs == ['Tech']


def test_df_ticker_profile():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE ticker_meta_profile (
            ticker TEXT PRIMARY KEY,
            sector TEXT,
            industry TEXT
        )
    """)
    cursor.execute("INSERT INTO ticker_meta_profile VALUES ('AAPL', 'Technology', 'Consumer Electronics')")
    conn.commit()

    with patch('utils.ticker_utils.get_sqlite_conn') as mock_conn:
        mock_conn.return_value.__enter__.return_value = conn
        df = df_ticker_profile(tickers=['AAPL'])
        assert not df.empty
        assert df.iloc[0]['ticker'] == 'AAPL'
        assert df.iloc[0]['sectorname'] == 'Technology'
        assert df.iloc[0]['primaryname'] == 'Consumer Electronics'

        empty_df = df_ticker_profile(tickers=['UNKNOWN'])
        assert empty_df.empty
