import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stock_mdb.scripts.check_xlk_dashboard import main

@patch("scripts.check_xlk_dashboard.get_db_prices")
@patch("scripts.check_xlk_dashboard.get_yf_prices")
@patch("sys.exit")
def test_check_xlk_dashboard_success(mock_sys_exit, mock_get_yf, mock_get_db):
    # Setup matching data
    mock_get_db.return_value = [
        {"date": "2026-07-06", "price": 120.00},
        {"date": "2026-07-07", "price": 121.50},
    ]
    mock_get_yf.return_value = {
        "2026-07-06": 120.00,
        "2026-07-07": 121.502  # Difference is 0.002, which is <= 0.01 (success)
    }
    
    main()
    
    # Check that sys.exit(0) was called
    mock_sys_exit.assert_called_once_with(0)

@patch("scripts.check_xlk_dashboard.get_db_prices")
@patch("scripts.check_xlk_dashboard.get_yf_prices")
@patch("sys.exit")
def test_check_xlk_dashboard_mismatch(mock_sys_exit, mock_get_yf, mock_get_db):
    # Setup mismatching data (difference is > 0.01)
    mock_get_db.return_value = [
        {"date": "2026-07-06", "price": 120.00},
        {"date": "2026-07-07", "price": 121.50},
    ]
    mock_get_yf.return_value = {
        "2026-07-06": 120.00,
        "2026-07-07": 121.55  # Difference is 0.05 (mismatch)
    }
    
    main()
    
    # Check that sys.exit(1) was called
    mock_sys_exit.assert_called_once_with(1)

@patch("scripts.check_xlk_dashboard.get_db_prices")
@patch("scripts.check_xlk_dashboard.get_yf_prices")
@patch("sys.exit")
def test_check_xlk_dashboard_missing_in_db(mock_sys_exit, mock_get_yf, mock_get_db):
    # Setup missing dates in database (will print warning but exit 0 if those present match)
    mock_get_db.return_value = [
        {"date": "2026-07-06", "price": 120.00},
    ]
    mock_get_yf.return_value = {
        "2026-07-06": 120.00,
        "2026-07-07": 121.50  # Missing in DB
    }
    
    main()
    
    # Check that sys.exit(0) was called because no mismatched values exist
    mock_sys_exit.assert_called_once_with(0)
