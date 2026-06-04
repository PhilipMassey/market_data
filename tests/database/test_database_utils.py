import pytest
import mongomock
from unittest.mock import patch
from database.database_utils import get_close_price_records

@pytest.fixture
def mock_db_close():
    """
    Fixture that creates a mock MongoDB collection and patches db_close in the target module.
    """
    client = mongomock.MongoClient()
    db = client['stock_market']
    mock_collection = db['market_data_close']
    
    with patch('database.database_utils.db_close', mock_collection):
        yield mock_collection

def test_get_close_price_records_empty_inputs(mock_db_close):
    """
    Test get_close_price_records with empty tickers or dates.
    """
    assert get_close_price_records([], []) == []
    assert get_close_price_records(["AAPL"], []) == []
    assert get_close_price_records([], ["2026-05-19"]) == []

def test_get_close_price_records_matching_query(mock_db_close):
    """
    Test that get_close_price_records returns only documents matching BOTH the tickers and dates.
    Also verifies that the '_id' field is excluded.
    """
    # 1. Populate the mock database
    mock_db_close.insert_many([
        {"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0},
        {"ticker": "AAPL", "date": "2026-05-20", "close_price": 152.0},
        {"ticker": "MSFT", "date": "2026-05-19", "close_price": 300.0},
        {"ticker": "MSFT", "date": "2026-05-21", "close_price": 305.0}, # Different date
        {"ticker": "GOOGL", "date": "2026-05-19", "close_price": 170.0}  # Different ticker
    ])

    # 2. Query for AAPL and MSFT on 2026-05-19 and 2026-05-20
    tickers = ["AAPL", "MSFT"]
    dates = ["2026-05-19", "2026-05-20"]
    
    records = get_close_price_records(tickers, dates)
    
    # 3. Assert correct matching
    assert len(records) == 3
    
    # Exclude _id must be verified
    for r in records:
        assert "_id" not in r
        
    assert {"ticker": "AAPL", "date": "2026-05-19", "close_price": 150.0} in records
    assert {"ticker": "AAPL", "date": "2026-05-20", "close_price": 152.0} in records
    assert {"ticker": "MSFT", "date": "2026-05-19", "close_price": 300.0} in records
