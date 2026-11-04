import os
from datetime import datetime
import pandas as pd
import pytest

from scripts.money_market_rollup import (
    fidelity_positions_filep,
    df_fidelity_positions_portfolio,
    write_df_to_file,
    money_market,
)


@pytest.fixture
def mock_download_dir(tmp_path, monkeypatch):
    """Sets scripts.money_market_rollup.download_dir to tmp_path."""
    monkeypatch.setattr('scripts.money_market_rollup.download_dir', str(tmp_path))
    return tmp_path


def test_fidelity_positions_filep_success(mock_download_dir):
    csv_file = mock_download_dir / "Portfolio_Positions_Oct-02-2026.csv"
    csv_file.write_text("Account name,Symbol,Current value\n")

    a_date, file_path = fidelity_positions_filep()
    assert a_date == datetime(2026, 10, 2)
    assert file_path == str(csv_file)


def test_fidelity_positions_filep_multiple_or_no_files_raises(mock_download_dir):
    # No files present
    with pytest.raises(Exception, match="File size is not 1"):
        fidelity_positions_filep()

    # Two files present
    f1 = mock_download_dir / "Portfolio_Positions_Oct-02-2026.csv"
    f2 = mock_download_dir / "Portfolio_Positions_Oct-09-2026.csv"
    f1.write_text("dummy")
    f2.write_text("dummy")

    with pytest.raises(Exception, match="File size is not 1"):
        fidelity_positions_filep()


def test_df_fidelity_positions_portfolio(mock_download_dir):
    csv_file = mock_download_dir / "Portfolio_Positions_Oct-02-2026.csv"
    csv_content = """Account number,Account name,Symbol,Current value
X1,Stocks,AAPL,$150.00
X1,Stocks,Pending Activity,$50.00
X1,Stocks,,$0.00
"""
    csv_file.write_text(csv_content)

    a_date, df = df_fidelity_positions_portfolio()
    assert a_date == datetime(2026, 10, 2)
    assert len(df) == 2  # Empty symbol row dropped
    assert 'FDRXX**' in df['Symbol'].values
    assert 'Pending Activity' not in df['Symbol'].values


def test_write_df_to_file(tmp_path):
    out_file = tmp_path / "test_out.txt"
    df = pd.DataFrame([
        {'Account name': 'Stocks', 'Current value': 100.0},
        {'Account name': 'Dividends', 'Current value': 200.0},
    ])

    write_df_to_file(df, str(out_file))

    assert out_file.exists()
    content = out_file.read_text()
    assert 'Account name' in content
    assert 'Stocks' in content
    assert 'Dividends' in content


def test_money_market(mock_download_dir):
    csv_file = mock_download_dir / "Portfolio_Positions_Oct-02-2026.csv"
    csv_content = """Account number,Account name,Symbol,Current value
X1,X Stocks,SPAXX**,$1000.00
X1,X Stocks,AAPL,$1500.00
D1,Dividends,FDRXX**,$2000.00
E1,ETFs Roth,CORE**,$500.00
S1,Shorts,Pending activity,$250.00
"""
    csv_file.write_text(csv_content)

    money_market()

    out_file = mock_download_dir / "Money Market.txt"
    assert out_file.exists()

    content = out_file.read_text()
    # Read back as DataFrame
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    header = lines[0]
    assert 'Account name' in header and 'Current value' in header

    # Verify rows and Total
    assert 'X Stocks' in content
    assert 'Dividends' in content
    assert 'ETFs Roth' in content
    assert 'Shorts' in content
    assert 'Total' in content
    assert '3750.0' in content  # 1000 + 2000 + 500 + 250
