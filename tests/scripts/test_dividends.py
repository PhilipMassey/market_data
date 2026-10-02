import os
import sys
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.dividends import (
    df_sum_symbol_div_amount,
    df_ungroup_symbol_div_amount,
    worksheet_update_with_df,
    worksheet_insert_ungrouped_with_df,
)


@pytest.fixture
def sample_accounts_history_csv(tmp_path):
    csv_file = tmp_path / "Accounts_History Q1.csv"
    csv_content = """Date,Action,Symbol,Description,Amount ($)
2026-01-15,DIVIDEND RECEIVED,AAPL,APPLE INC,50.00
2026-02-15,DIVIDEND RECEIVED,AAPL,APPLE INC,25.00
2026-03-10,DIVIDEND RECEIVED,MSFT,MICROSOFT CORP,100.00
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


def test_df_sum_symbol_div_amount(sample_accounts_history_csv):
    df = df_sum_symbol_div_amount(1, '2026', file_path=sample_accounts_history_csv)
    assert list(df.columns) == ['Quarter', 'Symbol', 'Dividend']
    assert len(df) == 2  # AAPL aggregated, MSFT

    aapl = df[df['Symbol'] == 'AAPL'].iloc[0]
    assert aapl['Dividend'] == 75.00
    assert aapl['Quarter'] == '1 2026'

    msft = df[df['Symbol'] == 'MSFT'].iloc[0]
    assert msft['Dividend'] == 100.00
    assert msft['Quarter'] == '1 2026'


def test_df_ungroup_symbol_div_amount(sample_accounts_history_csv):
    df = df_ungroup_symbol_div_amount(1, '2026', file_path=sample_accounts_history_csv)
    assert list(df.columns) == ['Quarter', 'Symbol', 'Dividend', 'Date']
    assert len(df) == 3  # Individual transactions sorted descending by Date

    symbols = list(df['Symbol'])
    dividends = list(df['Dividend'])
    dates = list(df['Date'])
    # Sorted descending: 2026-03-10, 2026-02-15, 2026-01-15
    assert symbols == ['MSFT', 'AAPL', 'AAPL']
    assert dividends == [100.0, 25.0, 50.0]
    assert dates == ['2026-03-10', '2026-02-15', '2026-01-15']
    assert all(q == '1 2026' for q in df['Quarter'])


def test_df_ungroup_symbol_div_amount_with_run_date(tmp_path):
    csv_file = tmp_path / "Accounts_History Q2.csv"
    csv_content = """Run Date,Action,Symbol,Description,Amount ($)
04/15/2026,DIVIDEND RECEIVED,CSWC,CAPITAL SOUTHWEST,34.04
"""
    csv_file.write_text(csv_content)
    df = df_ungroup_symbol_div_amount(2, '2026', file_path=str(csv_file))
    assert list(df.columns) == ['Quarter', 'Symbol', 'Dividend', 'Date']
    assert df.iloc[0]['Date'] == '04/15/2026'
    assert df.iloc[0]['Dividend'] == 34.04


def test_worksheet_update_with_df_column_a():
    mock_client = MagicMock()
    mock_workbook = MagicMock()
    mock_worksheet = MagicMock()
    mock_client.open.return_value = mock_workbook
    mock_workbook.get_worksheet_by_id.return_value = mock_worksheet

    df = pd.DataFrame({'Quarter': ['1 2026'], 'Symbol': ['AAPL'], 'Dividend': [75.0]})

    with patch('scripts.dividends.set_with_dataframe') as mock_set_df:
        worksheet_update_with_df("Dividends", 282663853, df, row=1, col=1, client=mock_client)
        mock_client.open.assert_called_once_with("Dividends")
        mock_workbook.get_worksheet_by_id.assert_called_once_with(282663853)
        mock_set_df.assert_called_once_with(
            mock_worksheet, df, row=1, col=1, include_index=False, include_column_header=True
        )


def test_worksheet_insert_ungrouped_with_df_column_e():
    mock_client = MagicMock()
    mock_workbook = MagicMock()
    mock_worksheet = MagicMock()
    mock_client.open.return_value = mock_workbook
    mock_workbook.get_worksheet_by_id.return_value = mock_worksheet

    df = pd.DataFrame({'Quarter': ['1 2026', '1 2026'], 'Symbol': ['AAPL', 'AAPL'], 'Dividend': [50.0, 25.0]})

    with patch('scripts.dividends.set_with_dataframe') as mock_set_df:
        worksheet_insert_ungrouped_with_df("Dividends", 282663853, df, row=1, col=5, client=mock_client)
        mock_client.open.assert_called_once_with("Dividends")
        mock_workbook.get_worksheet_by_id.assert_called_once_with(282663853)
        # col=5 corresponds to Column E
        mock_set_df.assert_called_once_with(
            mock_worksheet, df, row=1, col=5, include_index=False, include_column_header=True
        )
