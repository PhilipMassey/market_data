import pytest
from unittest.mock import patch
from stock_mdb.load_missing import find_and_load_missing_close_prices

@patch('stock_mdb.load_missing.download_and_insert_missing_close_prices')
def test_find_and_load_missing_close_prices(mock_download):
    """
    Verify that calling find_and_load_missing_close_prices invokes the
    download_and_insert_missing_close_prices function from market_data_close.
    """
    find_and_load_missing_close_prices()
    mock_download.assert_called_once()
