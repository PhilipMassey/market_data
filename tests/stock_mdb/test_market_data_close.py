import pytest
import pandas as pd
import mongomock
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
def mock_db_close():
    """
    Fixture that creates a mock MongoDB collection and patches db_close in the target module.
    """
    client = mongomock.MongoClient()
    db = client['stock_market']
    mock_collection = db['market_data_close']
    
    with patch('stock_mdb.market_data_close.db_close', mock_collection):
        yield mock_collection

def test_find_missing_dates_empty_inputs(mock_db_close):
    """
    Test find_missing_dates_in_db with empty input parameters.
    """
    assert find_missing_dates_in_db([], []) == {}
    assert find_missing_dates_in_db(["AAPL"], []) == {}
    assert find_missing_dates_in_db([], ["2026-05-19"]) == {}

def test_find_missing_dates_all_missing(mock_db_close):
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

def test_find_missing_dates_some_existing(mock_db_close):
    """
    Test when some records already exist in the database.
    """
    mock_db_close.insert_many([
        {"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0},
        {"ticker": "MSFT", "date": "2026-05-20", "close_price": 300.0}
    ])
    
    tickers = ["AAPL", "MSFT"]
    expected_dates = ["2026-05-19", "2026-05-20"]
    missing = find_missing_dates_in_db(tickers, expected_dates)
    
    assert missing == {
        "AAPL": ["2026-05-20"],
        "MSFT": ["2026-05-19"]
    }

def test_find_missing_dates_none_missing(mock_db_close):
    """
    Test when all expected records already exist in the database.
    """
    mock_db_close.insert_many([
        {"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0},
        {"ticker": "AAPL", "date": "2026-05-20", "close_price": 151.0},
        {"ticker": "MSFT", "date": "2026-05-19", "close_price": 299.0},
        {"ticker": "MSFT", "date": "2026-05-20", "close_price": 300.0}
    ])
    
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
    mock_db_close
):
    """
    Test the full workflow when missing data needs to be downloaded and inserted.
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
    mock_yf_download.return_value = MockYFData(close_df)
    
    # 3. Call the target function
    download_and_insert_missing_close_prices()
    
    # 4. Verify mock calls
    mock_get_calendar.assert_called_once()
    mock_get_all_tickers.assert_called_once()
    mock_yf_download.assert_called_once_with(["AAPL", "MSFT"], start="2026-05-19", end="2026-05-21", progress=False)
    
    # 5. Verify records were inserted in DB
    inserted = list(mock_db_close.find({}, {"_id": 0}))
    assert len(inserted) == 4
    
    # Check that entries exist with correct structure
    assert {"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0} in inserted
    assert {"ticker": "AAPL", "date": "2026-05-20", "close_price": 152.0} in inserted
    assert {"ticker": "MSFT", "date": "2026-05-19", "close_price": 300.0} in inserted
    assert {"ticker": "MSFT", "date": "2026-05-20", "close_price": 305.0} in inserted

@patch('stock_mdb.market_data_close.get_nyse_calendar_past_year')
@patch('stock_mdb.market_data_close.get_all_tickers')
@patch('yfinance.download')
def test_download_and_insert_missing_close_prices_no_missing(
    mock_yf_download,
    mock_get_all_tickers,
    mock_get_calendar,
    mock_db_close
):
    """
    Test that no download or insertion occurs if the database is already fully populated.
    """
    # 1. Setup mock calendar and tickers
    mock_get_calendar.return_value = ["2026-05-19"]
    mock_get_all_tickers.return_value = ["AAPL"]
    
    # 2. Populate the DB with the expected data
    mock_db_close.insert_one({"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0})
    
    # 3. Call the function
    download_and_insert_missing_close_prices()
    
    # 4. Verify yfinance was not called
    mock_yf_download.assert_not_called()
    
    # 5. Verify DB contents remain identical
    inserted = list(mock_db_close.find({}, {"_id": 0}))
    assert inserted == [{"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0}]
