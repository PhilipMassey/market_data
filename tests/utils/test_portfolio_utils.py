import pytest
import pandas as pd
from utils.portfolio_utils import (
    is_cash,
    filter_out_cash_symbols,
    map_account_name,
    normalize_fidelity_columns,
    clean_numeric_columns,
    extract_date_from_filename,
)


def test_is_cash():
    assert is_cash("SPAXX**") is True
    assert is_cash("FCASH") is True
    assert is_cash("Pending Activity") is True
    assert is_cash("Money Market") is True
    assert is_cash("AAPL") is False
    assert is_cash("") is False


def test_filter_out_cash_symbols():
    df = pd.DataFrame({
        'Symbol': ['AAPL', 'SPAXX**', 'Pending Activity', 'MSFT', '', None]
    })
    filtered = filter_out_cash_symbols(df)
    assert list(filtered['Symbol']) == ['AAPL', 'MSFT']


def test_map_account_name():
    assert map_account_name("Individual - Stocks") == "Stocks"
    assert map_account_name("Z Dividends") == "Dividends"
    assert map_account_name("ETFs Roth") == "ETFs"
    assert map_account_name("Z Shorts") == "Shorts"
    assert map_account_name("International") == "International"
    assert map_account_name("Other Account") == "Other Account"


def test_normalize_fidelity_columns():
    df = pd.DataFrame({'Account name': ['Stocks'], 'Current value': ['$100.00']})
    norm_df = normalize_fidelity_columns(df)
    assert 'Account Name' in norm_df.columns
    assert 'Current Value' in norm_df.columns


def test_clean_numeric_columns():
    df = pd.DataFrame({
        'Current Value': ['$1,250.50'],
        'Percent Of Account': ['12.5%'],
        'Quantity': ['1,000'],
    })
    clean_numeric_columns(
        df,
        dollar_cols=['Current Value'],
        percent_cols=['Percent Of Account'],
        numeric_cols=['Quantity'],
    )
    assert df['Current Value'].iloc[0] == 1250.50
    assert df['Percent Of Account'].iloc[0] == 12.5
    assert df['Quantity'].iloc[0] == 1000.0


def test_extract_date_from_filename():
    assert extract_date_from_filename("Portfolio_Positions_Jun-07-2026.csv") == "2026-06-07"

