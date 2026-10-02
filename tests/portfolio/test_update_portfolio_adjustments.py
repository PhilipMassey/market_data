import os
import sys
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from portfolio.update_portfolio_adjustments import (
    df_fidelity_portfolios,
    df_clean_fidelity_for_worksheet,
    update_fidelity_positions_worksheet,
    adjustments_update_fidelity_percentages,
    worksheet_update_with_df,
    DCT_ADJUSTMENT_ID,
    PORTFOLIOS
)


@pytest.fixture
def sample_fidelity_csv_file(tmp_path):
    csv_file = tmp_path / "Portfolio_Positions_Sep-29-2026.csv"
    csv_content = """Account Name,Symbol,Quantity,Last Price,Current Value,Cost Basis Total,Average Cost Basis
Individual - Stocks,AAPL,10,$150.00,"$1,500.00","$1,200.00",$120.00
Individual - Stocks,MSFT,5,$300.00,"$1,500.00","$1,000.00",$200.00
Roth IRA - Dividends,ADX,50,$20.00,"$1,000.00",$900.00,$18.00
Roth IRA - Dividends,AAPL,5,$150.00,$750.00,$600.00,$120.00
Individual - ETFs,SPY,2,$500.00,"$1,000.00",$800.00,$400.00
Individual - Stocks,CORE**,1000,$1.00,"$1,000.00","$1,000.00",$1.00
Individual - Stocks,Pending Activity,0,$0.00,$0.00,$0.00,$0.00
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


def test_df_fidelity_portfolios_from_csv(sample_fidelity_csv_file):
    df = df_fidelity_portfolios(sample_fidelity_csv_file)

    # Cash and Pending activity should be filtered out
    assert 'CORE**' not in df['Symbol'].values
    assert 'Pending Activity' not in df['Symbol'].values
    assert 'PENDING ACTIVITY' not in df['Symbol'].values

    # Check mapped account categories
    stocks_df = df[df['Account name'] == 'Stocks']
    assert set(stocks_df['Symbol']) == {'AAPL', 'MSFT'}

    div_df = df[df['Account name'] == 'Dividends']
    assert set(div_df['Symbol']) == {'ADX', 'AAPL'}

    etf_df = df[df['Account name'] == 'ETFs']
    assert set(etf_df['Symbol']) == {'SPY'}

    # Values for AAPL in Stocks: $1,500.00, Cost: $1,200.00
    aapl_stocks = stocks_df[stocks_df['Symbol'] == 'AAPL'].iloc[0]
    assert aapl_stocks['Current value'] == 1500.0
    assert aapl_stocks['Cost basis total'] == 1200.0


def test_df_clean_fidelity_for_worksheet(sample_fidelity_csv_file):
    raw_df = pd.read_csv(sample_fidelity_csv_file)
    sum_df = df_clean_fidelity_for_worksheet(raw_df)

    # Verify cash/pending excluded
    assert 'CORE**' not in sum_df['Symbol'].values
    assert 'Pending Activity' not in sum_df['Symbol'].values

    # Symbols aggregated across accounts: AAPL, ADX, MSFT, SPY
    assert list(sum_df['Symbol']) == ['AAPL', 'ADX', 'MSFT', 'SPY']

    # AAPL was in both Stocks (10 qty, $1500) and Dividends (5 qty, $750) -> sum: 15 qty, $2250
    aapl_row = sum_df[sum_df['Symbol'] == 'AAPL'].iloc[0]
    assert aapl_row['Quantity'] == 15.0
    assert aapl_row['Current Value'] == 2250.0
    assert aapl_row['Cost Basis Total'] == 1800.0
    assert pytest.approx(aapl_row['Average Cost Basis']) == 120.0


def test_update_fidelity_positions_worksheet(sample_fidelity_csv_file):
    raw_df = pd.read_csv(sample_fidelity_csv_file)
    mock_gc = MagicMock()

    with patch('portfolio.update_portfolio_adjustments.worksheet_update_with_df') as mock_update:
        update_fidelity_positions_worksheet(
            raw_df=raw_df,
            workbook_url="https://docs.google.com/test",
            gc=mock_gc
        )

        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert args[0] == mock_gc
        assert args[1] == "https://docs.google.com/test"
        assert args[2] == DCT_ADJUSTMENT_ID['Fidelity Positions']  # 1550649944
        df_uploaded = args[3]
        assert list(df_uploaded['Symbol']) == ['AAPL', 'ADX', 'MSFT', 'SPY']


def test_df_fidelity_portfolios_fallback_sqlite():
    mock_sqlite_data = pd.DataFrame([
        {'Symbol': 'AAPL', 'Account name': 'Stocks', 'Current value': 1000.0, 'Cost basis total': 800.0},
        {'Symbol': 'ADX', 'Account name': 'Dividends', 'Current value': 400.0, 'Cost basis total': 350.0},
    ])
    with patch('portfolio.update_portfolio_adjustments.df_fidelity_positions_portfolio', side_effect=FileNotFoundError("No CSV")), \
         patch('portfolio.update_portfolio_adjustments.init_sqlite_db'), \
         patch('portfolio.update_portfolio_adjustments.get_sqlite_conn') as mock_conn:

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [2]
        mock_context = MagicMock()
        mock_context.__enter__.return_value = MagicMock(cursor=MagicMock(return_value=mock_cursor))
        mock_conn.return_value = mock_context

        with patch('pandas.read_sql_query', return_value=mock_sqlite_data):
            df = df_fidelity_portfolios()
            assert len(df) == 2
            assert set(df['Symbol']) == {'AAPL', 'ADX'}


def test_adjustments_update_fidelity_percentages():
    sample_df = pd.DataFrame([
        {'Symbol': 'AAPL', 'Account name': 'Stocks', 'Current value': 200.0, 'Cost basis total': 100.0},
        {'Symbol': 'MSFT', 'Account name': 'Stocks', 'Current value': 800.0, 'Cost basis total': 800.0},
    ])
    
    mock_gc = MagicMock()
    
    with patch('portfolio.update_portfolio_adjustments.worksheet_update_with_df') as mock_update:
        adjustments_update_fidelity_percentages(
            fidelity_df=sample_df,
            workbook_url="https://docs.google.com/test",
            portfolios=['Stocks'],
            gc=mock_gc
        )

        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        # args: (gc, workbook_url, worksheet_id, df_update)
        assert args[0] == mock_gc
        assert args[1] == "https://docs.google.com/test"
        assert args[2] == DCT_ADJUSTMENT_ID['Stocks']

        df_update = args[3]
        assert list(df_update.columns) == ['Symbol', 'Current value %', 'Current return %']
        
        # Check percentage calculations
        # AAPL: 200 / 1000 = 0.20, return: (200 - 100) / 100 = 1.0 (100%)
        # MSFT: 800 / 1000 = 0.80, return: (800 - 800) / 800 = 0.0 (0%)
        aapl_row = df_update[df_update['Symbol'] == 'AAPL'].iloc[0]
        assert pytest.approx(aapl_row['Current value %']) == 0.20
        assert pytest.approx(aapl_row['Current return %']) == 1.0

        msft_row = df_update[df_update['Symbol'] == 'MSFT'].iloc[0]
        assert pytest.approx(msft_row['Current value %']) == 0.80
        assert pytest.approx(msft_row['Current return %']) == 0.0


def test_worksheet_update_with_df():
    mock_gc = MagicMock()
    mock_workbook = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.title = "Stocks"
    
    mock_gc.open_by_url.return_value = mock_workbook
    mock_workbook.get_worksheet_by_id.return_value = mock_worksheet
    
    df = pd.DataFrame({'Symbol': ['AAPL'], 'Current value %': [0.5], 'Current return %': [0.1]})
    
    with patch('portfolio.update_portfolio_adjustments.set_with_dataframe') as mock_set_df:
        mock_set_df.return_value = {'updatedCells': 6}
        
        result = worksheet_update_with_df(
            gc=mock_gc,
            workbook_url="https://docs.google.com/test",
            worksheet_id=569122364,
            df=df
        )

        mock_workbook.get_worksheet_by_id.assert_called_once_with(569122364)
        mock_worksheet.batch_clear.assert_called_once_with(["A1:Z69"])
        mock_set_df.assert_called_once_with(
            mock_worksheet, df, row=1, col=1, include_index=False, include_column_header=True
        )
        assert result == {'updatedCells': 6}
