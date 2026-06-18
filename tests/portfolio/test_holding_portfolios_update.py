import os
import pytest
import sqlite3
import pandas as pd
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from portfolio.holding_portfolios_update import (
    extract_date_from_filename,
    df_fidelity_positions_aggregate_columns,
    process_fidelity_export,
    process_seeking_alpha_exports,
    compare_holdings_and_write_mismatches,
    run
)

def test_extract_date_from_filename():
    # Test valid filename
    assert extract_date_from_filename("Portfolio_Positions_Jun-07-2026.csv") == "2026-06-07"
    assert extract_date_from_filename("/some/path/Portfolio_Positions_Jan-15-2024.csv") == "2024-01-15"
    assert extract_date_from_filename("Portfolio_Positions_Dec-31-1999.csv") == "1999-12-31"

    # Test invalid filenames
    with pytest.raises(ValueError, match="Filename does not match expected format"):
        extract_date_from_filename("Portfolio_Positions.csv")
    with pytest.raises(ValueError, match="Filename does not match expected format"):
        extract_date_from_filename("Portfolio_Positions_07-06-2026.csv")
    with pytest.raises(ValueError, match="Could not parse date"):
        extract_date_from_filename("Portfolio_Positions_Foo-07-2026.csv")

def test_df_fidelity_positions_aggregate_columns():
    # Create sample dataframe with duplicates, BOM, formatting, etc.
    data = {
        'Account Number': ['X12345', 'X12345', 'Y67890', 'Y67890'],
        'Account Name': ['Acc1', 'Acc1', 'Acc2', 'Acc2'],
        'Symbol': ['AAPL', 'AAPL', 'MSFT', 'Pending activity'],
        'Description': ['Apple Inc', 'Apple Inc', 'Microsoft', 'Pending'],
        'Quantity': ['10', '15', '5', ''],
        'Last Price': ['$150.00', '$150.00', '$400.00', ''],
        'Current Value': ['$1,500.00', '$2,250.00', '$2,000.00', '-$100.00'],
        'Cost Basis Total': ['$1,400.00', '$2,100.00', '$1,800.00', ''],
        'Average Cost Basis': ['$140.00', '$140.00', '$360.00', ''],
        'Percent Of Account': ['1.5%', '2.2%', '10.0%', '']
    }
    df = pd.DataFrame(data)

    agg_df = df_fidelity_positions_aggregate_columns(df)

    # Verify rows with Null/Empty Symbol are removed, but Pending activity is retained
    assert len(agg_df) == 3
    assert set(agg_df['Symbol'].tolist()) == {'AAPL', 'MSFT', 'Pending activity'}

    # Verify AAPL aggregation:
    # Quantity: 10 + 15 = 25
    # Current Value: 1500 + 2250 = 3750
    # Cost Basis Total: 1400 + 2100 = 3500
    # Last Price: first ('$150.00' -> 150.0)
    # Average Cost Basis: mean (140.0)
    # Percent Of Account: mean (1.85)
    aapl_row = agg_df[agg_df['Symbol'] == 'AAPL'].iloc[0]
    assert aapl_row['Account Name'] == 'Acc1'
    assert aapl_row['Quantity'] == 25.0
    assert aapl_row['Current Value'] == 3750.0
    assert aapl_row['Cost Basis Total'] == 3500.0
    assert aapl_row['Last Price'] == 150.0
    assert aapl_row['Average Cost Basis'] == 140.0
    assert aapl_row['Percent Of Account'] == 1.85

    # Verify MSFT values
    msft_row = agg_df[agg_df['Symbol'] == 'MSFT'].iloc[0]
    assert msft_row['Account Name'] == 'Acc2'
    assert msft_row['Quantity'] == 5.0
    assert msft_row['Current Value'] == 2000.0
    assert msft_row['Cost Basis Total'] == 1800.0
    assert msft_row['Last Price'] == 400.0
    assert msft_row['Average Cost Basis'] == 360.0
    assert msft_row['Percent Of Account'] == 10.0

@pytest.fixture
def mock_sqlite_db():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fidelity_positions (
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            quantity REAL,
            average_cost_basis REAL,
            cost_basis_total REAL,
            current_value REAL,
            account_name TEXT,
            last_price REAL,
            percent_of_account REAL,
            PRIMARY KEY (date, symbol)
        )
    """)
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    with patch('portfolio.holding_portfolios_update.get_sqlite_conn', _get_conn), \
         patch('portfolio.holding_portfolios_update.init_sqlite_db'):
        yield conn
    conn.close()

def test_process_fidelity_export(mock_sqlite_db, tmp_path):
    # Create a dummy CSV file with various accounts for roll up testing
    csv_file = tmp_path / "Portfolio_Positions_Jun-07-2026.csv"
    data = (
        "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,Current Value,Today's Gain/Loss Dollar,Today's Gain/Loss Percent,Total Gain/Loss Dollar,Total Gain/Loss Percent,Percent Of Account,Cost Basis Total,Average Cost Basis,Type\n"
        "X123,Stocks,AAPL,Apple Inc,10,$150.00,+$2.00,$1500.00,+$20.00,+1.3%,+$100.00,+7.14%,1.5%,$1400.00,$140.00,Margin\n"
        "X123,X Stocks,MSFT,Microsoft,5,$400.00,+$5.00,$2000.00,+$25.00,+1.0%,+$200.00,+11.11%,2.0%,$1800.00,$360.00,Margin\n"
        "X123,ETFs Roth,SPY,SPDR S&P 500,2,$500.00,+$1.00,$1000.00,+$2.00,+0.2%,+$50.00,+5.26%,1.0%,$950.00,$475.00,Margin\n"
        "X123,Z ETFs,QQQ,Invesco QQQ,3,$450.00,+$2.00,$1350.00,+$6.00,+0.4%,+$70.00,+5.47%,1.35%,$1280.00,$426.67,Margin\n"
        "X123,Z ETFs,SPY,SPDR S&P 500,1,$500.00,+$1.00,$500.00,+$1.00,+0.2%,+$25.00,+5.26%,0.5%,$475.00,$475.00,Margin\n"
        "X123,Stocks,SPAXX**,Cash,1000,$1.00,$0.00,$1000.00,$0.00,0.0%,$0.00,0.0%,1.0%,$1000.00,$1.00,Cash\n"
    )
    csv_file.write_text(data)

    # Process
    with patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        process_fidelity_export(str(csv_file))

    # Read from in-memory SQLite and check database insertions
    cursor = mock_sqlite_db.cursor()
    cursor.execute("SELECT symbol FROM fidelity_positions ORDER BY symbol")
    rows = cursor.fetchall()

    # All unique symbols (including cash/core SPAXX**) should be in db
    assert len(rows) == 5
    assert [r[0] for r in rows] == ['AAPL', 'MSFT', 'QQQ', 'SPAXX**', 'SPY']

    # Verify Stocks.csv is created and has AAPL and MSFT (from Stocks and X Stocks), and SPAXX** is excluded
    stocks_csv = tmp_path / "tickers" / "Holding" / "Stocks.csv"
    assert stocks_csv.exists()
    df_stocks = pd.read_csv(stocks_csv)
    assert df_stocks['Symbol'].tolist() == ['AAPL', 'MSFT']

    # Verify ETFs.csv is created and has QQQ and SPY (from ETFs Roth and Z ETFs), sorted and deduplicated
    etfs_csv = tmp_path / "tickers" / "Holding" / "ETFs.csv"
    assert etfs_csv.exists()
    df_etfs = pd.read_csv(etfs_csv)
    assert df_etfs['Symbol'].tolist() == ['QQQ', 'SPY']

def test_run_no_files():
    with patch('glob.glob', return_value=[]), \
         pytest.raises(SystemExit) as excinfo:
        run()
    assert excinfo.value.code == 1

def test_run_multiple_files():
    with patch('glob.glob', return_value=['file1.csv', 'file2.csv']), \
         pytest.raises(SystemExit) as excinfo:
        run()
    assert excinfo.value.code == 1

def test_run_one_file():
    with patch('glob.glob', return_value=['/Downloads/Portfolio_Positions_Jun-07-2026.csv']), \
         patch('portfolio.holding_portfolios_update.process_fidelity_export') as mock_process, \
         patch('portfolio.holding_portfolios_update.process_seeking_alpha_exports', return_value=True) as mock_sa, \
         patch('portfolio.holding_portfolios_update.compare_holdings_and_write_mismatches') as mock_comp:
        run()
        mock_process.assert_called_once_with('/Downloads/Portfolio_Positions_Jun-07-2026.csv')
        mock_sa.assert_called_once()
        mock_comp.assert_called_once()

def test_process_seeking_alpha_exports_no_files(tmp_path):
    with patch('glob.glob', return_value=[]), \
         patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        res = process_seeking_alpha_exports()
        assert res is True
        # Verify no files were created
        target_dir = tmp_path / "tickers" / "Seeking_Alpha"
        assert not target_dir.exists()

def test_process_seeking_alpha_exports_success(tmp_path):
    # Setup mock Downloads dir with some Excel files
    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir()
    
    file_old = downloads_dir / "Current Dividends 2026-06-12.xlsx"
    file_new = downloads_dir / "Current Dividends 2026-06-14.xlsx"
    file_other = downloads_dir / "Top Stocks 2026-06-14.xlsx"
    
    # We will mock pandas.read_excel to return different DataFrames depending on the file
    def mock_read_excel(file_path, *args, **kwargs):
        name = os.path.basename(file_path)
        if name == "Current Dividends 2026-06-14.xlsx":
            return pd.DataFrame({'Symbol': ['AGNC', 'adx', 'JEPQ', '', 'JEPQ']})  # Has duplicates, lowercase, empty
        elif name == "Current Dividends 2026-06-12.xlsx":
            # This is the older one, should NOT be read
            raise AssertionError("Should not read older file version!")
        elif name == "Top Stocks 2026-06-14.xlsx":
            return pd.DataFrame({'Symbol': ['AAPL', 'MSFT']})
        else:
            raise ValueError(f"Unexpected file path: {file_path}")

    # Patch glob.glob to return all three files
    files = [str(file_old), str(file_new), str(file_other)]
    
    with patch('glob.glob', return_value=files), \
         patch('pandas.read_excel', side_effect=mock_read_excel), \
         patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        res = process_seeking_alpha_exports()
        assert res is True
        
        # Verify output CSVs
        sa_dir = tmp_path / "tickers" / "Seeking_Alpha"
        holding_dir = tmp_path / "tickers" / "Holding"
        assert sa_dir.exists()
        assert holding_dir.exists()
        
        # Check Current Dividends (should be in Holding)
        div_csv = holding_dir / "Current Dividends.csv"
        assert div_csv.exists()
        df_div = pd.read_csv(div_csv)
        assert df_div.columns.tolist() == ['Symbol']
        # Expect unique, uppercase, non-empty, sorted alphabetically: ADX, AGNC, JEPQ
        assert df_div['Symbol'].tolist() == ['ADX', 'AGNC', 'JEPQ']
        
        # Check Top Stocks (should be in Seeking_Alpha)
        top_csv = sa_dir / "Top Stocks.csv"
        assert top_csv.exists()
        df_top = pd.read_csv(top_csv)
        assert df_top['Symbol'].tolist() == ['AAPL', 'MSFT']

def test_process_seeking_alpha_exports_missing_symbol_column(tmp_path):
    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir()
    
    file_bad = downloads_dir / "Current Dividends 2026-06-14.xlsx"
    file_good = downloads_dir / "Top Stocks 2026-06-14.xlsx"
    
    def mock_read_excel(file_path, *args, **kwargs):
        name = os.path.basename(file_path)
        if name == "Current Dividends 2026-06-14.xlsx":
            # Missing 'Symbol' column
            return pd.DataFrame({'WrongColumn': ['AGNC']})
        elif name == "Top Stocks 2026-06-14.xlsx":
            return pd.DataFrame({'Symbol': ['AAPL']})
        else:
            raise ValueError(f"Unexpected file path: {file_path}")

    files = [str(file_bad), str(file_good)]
    
    with patch('glob.glob', return_value=files), \
         patch('pandas.read_excel', side_effect=mock_read_excel), \
         patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        res = process_seeking_alpha_exports()
        # Should return False overall because one file failed
        assert res is False
        
        # Verify that Top Stocks was still written successfully
        sa_dir = tmp_path / "tickers" / "Seeking_Alpha"
        holding_dir = tmp_path / "tickers" / "Holding"
        assert sa_dir.exists()
        
        top_csv = sa_dir / "Top Stocks.csv"
        assert top_csv.exists()
        df_top = pd.read_csv(top_csv)
        assert df_top['Symbol'].tolist() == ['AAPL']
        
        # Verify that Current Dividends was NOT written to Holding
        div_csv = holding_dir / "Current Dividends.csv"
        assert not div_csv.exists()

def test_compare_holdings_and_write_mismatches_with_differences(tmp_path):
    holding_dir = tmp_path / "tickers" / "Holding"
    holding_dir.mkdir(parents=True)
    
    # 1. Create matching/mismatching files
    # Current Stocks: AAPL, GOOG, MSFT
    # Stocks: AAPL, MSFT, TSLA
    # Mismatch: GOOG only in Current, TSLA only in target
    pd.DataFrame({'Symbol': ['AAPL', 'GOOG', 'MSFT']}).to_csv(holding_dir / "Current Stocks.csv", index=False)
    pd.DataFrame({'Symbol': ['AAPL', 'MSFT', 'TSLA']}).to_csv(holding_dir / "Stocks.csv", index=False)
    
    # Current ETFs: QQQ, SPY
    # ETFs: QQQ, SPY
    # Match perfectly
    pd.DataFrame({'Symbol': ['QQQ', 'SPY']}).to_csv(holding_dir / "Current ETFs.csv", index=False)
    pd.DataFrame({'Symbol': ['QQQ', 'SPY']}).to_csv(holding_dir / "ETFs.csv", index=False)
    
    downloads_dir = tmp_path / "Downloads"
    
    original_expanduser = os.path.expanduser
    def mock_expanduser(path):
        if path == '~/Downloads':
            return str(downloads_dir)
        return original_expanduser(path)
    
    with patch('os.path.expanduser', side_effect=mock_expanduser), \
         patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        compare_holdings_and_write_mismatches(str(tmp_path))
        
    # Verify report was written
    report_file = downloads_dir / "mismatches.txt"
    assert report_file.exists()
    
    content = report_file.read_text()
    assert "Category: Stocks" in content
    assert "Only in 'Current Stocks' (Seeking Alpha) [1 symbols]:" in content
    assert "GOOG" in content
    assert "Only in 'Stocks' (Fidelity) [1 symbols]:" in content
    assert "TSLA" in content
    assert "Category: ETFs" not in content  # Matching categories shouldn't be detailed as mismatching

def test_compare_holdings_and_write_mismatches_perfect_match(tmp_path):
    holding_dir = tmp_path / "tickers" / "Holding"
    holding_dir.mkdir(parents=True)
    
    pd.DataFrame({'Symbol': ['AAPL']}).to_csv(holding_dir / "Current Stocks.csv", index=False)
    pd.DataFrame({'Symbol': ['AAPL']}).to_csv(holding_dir / "Stocks.csv", index=False)
    
    downloads_dir = tmp_path / "Downloads"
    
    original_expanduser = os.path.expanduser
    def mock_expanduser(path):
        if path == '~/Downloads':
            return str(downloads_dir)
        return original_expanduser(path)
    
    with patch('os.path.expanduser', side_effect=mock_expanduser), \
         patch('portfolio.holding_portfolios_update.project_root', str(tmp_path)):
        compare_holdings_and_write_mismatches(str(tmp_path))
        
    report_file = downloads_dir / "mismatches.txt"
    assert report_file.exists()
    content = report_file.read_text()
    assert "All categories match perfectly. No mismatches found!" in content

