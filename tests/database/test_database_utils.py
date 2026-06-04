import pytest
import mongomock
from datetime import datetime
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
    Test that get_close_price_records returns matching documents in the wide format,
    correctly converting dates and projecting only requested tickers.
    """
    # 1. Populate the mock database with wide format documents
    mock_db_close.insert_many([
        {
            "Date": datetime(2026, 5, 19, 0, 0),
            "AAPL": 150.0,
            "MSFT": 300.0,
            "GOOGL": 170.0
        },
        {
            "Date": datetime(2026, 5, 20, 0, 0),
            "AAPL": 152.0,
            "MSFT": 302.0
        },
        {
            "Date": datetime(2026, 5, 21, 0, 0),
            "AAPL": 153.0,
            "GOOGL": 172.0
        }
    ])

    # 2. Query for AAPL and MSFT on 2026-05-19 and 2026-05-20
    tickers = ["AAPL", "MSFT"]
    dates = ["2026-05-19", "2026-05-20"]
    
    records = get_close_price_records(tickers, dates)
    
    # 3. Assert correct matching and projection
    assert len(records) == 2
    
    # Exclude _id must be verified
    for r in records:
        assert "_id" not in r
        assert "Date" in r
        
    # Check that GOOGL was excluded and wide dict values are preserved
    assert {"Date": "2026-05-19", "AAPL": 150.0, "MSFT": 300.0} in records
    assert {"Date": "2026-05-20", "AAPL": 152.0, "MSFT": 302.0} in records
