import os
import sys
import glob
import argparse
from typing import Optional, Tuple
import pandas as pd
import numpy as np
import gspread
from gspread_dataframe import set_with_dataframe

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from portfolio.holding_portfolios_update import (
    df_fidelity_positions_aggregate_columns,
    extract_date_from_filename
)

PORTFOLIO_ADJUSTMENTS_URL = "https://docs.google.com/spreadsheets/d/1bTsH3cjQDGR-Mlnq-bypRqhGIHJApKKJgsgXWSemur4/edit#gid=0"
SERVICE_ACCOUNT_FILE = os.path.expanduser("~/.config/gspread/service_account.json")

PORTFOLIOS = ['Dividends', 'ETFs', 'International', 'Shorts', 'Stocks']

DCT_ADJUSTMENT_ID = {
    'Alpha Picks': 0,
    'PRO': 1900636367,
    'AP Values': 608820938,
    'Dividends': 1022929694,
    'ETFs': 84489004,
    'International': 1766130281,
    'Stocks': 569122364,
    'Treasuries': 1853636016,
    'Shorts': 2049612117,
    'Fidelity Positions': 1550649944,
}


def get_gspread_client(credentials_file: str = SERVICE_ACCOUNT_FILE) -> gspread.Client:
    """
    Initializes and returns a Google Sheets API client using service account credentials.
    """
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"Google service account file not found at: {credentials_file}")
    return gspread.service_account(filename=credentials_file)


def worksheet_update_with_df(
    gc: gspread.Client,
    workbook_url: str,
    worksheet_id: int,
    df: pd.DataFrame,
    clear_range: str = "A1:Z69"
):
    """
    Updates a specific Google Worksheet by ID with the given DataFrame.
    Preserves existing formatting and formulas at or below row 70 by clearing only A1:Z69.
    """
    workbook = gc.open_by_url(workbook_url)
    worksheet = workbook.get_worksheet_by_id(worksheet_id)
    # Clear old data range above the formula row (row 70) while preserving formatting
    worksheet.batch_clear([clear_range])
    result = set_with_dataframe(worksheet, df, row=1, col=1, include_index=False, include_column_header=True)
    print(f"\tUpdated worksheet '{worksheet.title}' (ID {worksheet_id}) with {len(df)} rows.")
    return result


def get_latest_fidelity_csv(downloads_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    Finds the most recent Portfolio_Positions_*.csv file in the downloads directory.
    Returns (date_str, file_path).
    """
    if downloads_dir is None:
        downloads_dir = os.path.expanduser('~/Downloads')
    search_pattern = os.path.join(downloads_dir, 'Portfolio_Positions_*.csv')
    files = glob.glob(search_pattern)
    if not files:
        raise FileNotFoundError(f"No Portfolio_Positions_*.csv files found in: {downloads_dir}")
    latest_file = sorted(files)[-1]
    date_str = extract_date_from_filename(latest_file)
    return date_str, latest_file


def df_fidelity_positions_portfolio(file_path: Optional[str] = None) -> Tuple[str, pd.DataFrame]:
    """
    Reads a Fidelity CSV export file and performs initial cleaning.
    """
    if file_path is None:
        date_str, file_path = get_latest_fidelity_csv()
    else:
        date_str = extract_date_from_filename(file_path)

    fidelity_df = pd.read_csv(file_path, header=0, index_col=False, encoding='utf-8-sig')
    fidelity_df = fidelity_df.dropna(how='all', subset=['Symbol'])
    fidelity_df['Symbol'] = fidelity_df['Symbol'].replace('Pending Activity', 'FDRXX**')
    return date_str, fidelity_df


def df_clean_fidelity_for_worksheet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw Fidelity CSV export data and aggregates by Symbol across all accounts
    for the 'Fidelity Positions' worksheet.
    """
    df = df.copy()

    # Column name mapping
    column_mapping = {
        'Account name': 'Account Name',
        'Account number': 'Account Number',
        'Current value': 'Current Value',
        'Cost basis total': 'Cost Basis Total',
        'Average cost basis': 'Average Cost Basis',
        'Last price': 'Last Price',
        'Percent of account': 'Percent Of Account',
    }
    df.rename(columns=column_mapping, inplace=True)

    # Filter invalid symbols and cash/pending
    if 'Symbol' not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=['Symbol'])
    df['Symbol'] = df['Symbol'].astype(str).str.strip()
    df = df[df['Symbol'] != '']
    df = df[~df['Symbol'].str.endswith('**')]
    df = df[~df['Symbol'].str.upper().isin(['PENDING ACTIVITY', 'PENDING', 'FCASH', 'CASH'])]

    # Clean numeric columns
    for col in ['Current Value', 'Cost Basis Total', 'Average Cost Basis', 'Quantity']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Quantity' not in df.columns:
        df['Quantity'] = 0.0

    sum_df = df.groupby('Symbol').agg({
        'Current Value': 'sum',
        'Cost Basis Total': 'sum',
        'Quantity': 'sum',
        'Average Cost Basis': 'mean'
    }).reset_index()

    sum_df['Average Cost Basis'] = sum_df['Average Cost Basis'].round(2)
    sum_df = sum_df.sort_values(by='Symbol').reset_index(drop=True)
    return sum_df


def update_fidelity_positions_worksheet(
    raw_df: pd.DataFrame,
    workbook_url: str = PORTFOLIO_ADJUSTMENTS_URL,
    gc: Optional[gspread.Client] = None
):
    """
    Aggregates all Fidelity positions by Symbol across all accounts from the CSV,
    and updates the 'Fidelity Positions' worksheet.
    """
    if gc is None:
        gc = get_gspread_client()

    worksheet_id = DCT_ADJUSTMENT_ID.get('Fidelity Positions')
    if not worksheet_id:
        print("Skipping 'Fidelity Positions' worksheet update (ID not found).")
        return

    sum_df = df_clean_fidelity_for_worksheet(raw_df)
    if sum_df.empty:
        print("\tNo valid positions found for 'Fidelity Positions' worksheet.")
        return

    # Clean NaNs / infinities
    sum_df = sum_df.replace([np.inf, -np.inf], np.nan).fillna('')

    print(f"Updating 'Fidelity Positions' worksheet (ID {worksheet_id}) with {len(sum_df)} aggregated tickers.")
    worksheet_update_with_df(gc, workbook_url, worksheet_id, sum_df)


def df_fidelity_portfolios(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Returns aggregated Fidelity portfolio positions mapped to account categories:
    Dividends, ETFs, International, Shorts, Stocks.

    Prioritizes loading directly from the Fidelity Positions CSV
    (from file_path or ~/Downloads/Portfolio_Positions_*.csv).
    Falls back to SQLite fidelity_positions table if no CSV is available.
    """
    try:
        a_date, fidelity_df = df_fidelity_positions_portfolio(file_path)
        print(f"Loaded Fidelity positions directly from CSV ({a_date}).")

        # Normalize column names to Title Case for aggregation
        column_mapping = {
            'Account name': 'Account Name',
            'Account number': 'Account Number',
            'Current value': 'Current Value',
            'Cost basis total': 'Cost Basis Total',
            'Average cost basis': 'Average Cost Basis',
            'Last price': 'Last Price',
            'Percent of account': 'Percent Of Account',
        }
        fidelity_df.rename(columns=column_mapping, inplace=True)

        # Filter cash and pending entries
        fidelity_df = fidelity_df.dropna(subset=['Symbol'])
        fidelity_df['Symbol'] = fidelity_df['Symbol'].astype(str).str.strip()
        fidelity_df = fidelity_df[fidelity_df['Symbol'] != '']
        fidelity_df = fidelity_df[~fidelity_df['Symbol'].str.endswith('**')]
        fidelity_df = fidelity_df[~fidelity_df['Symbol'].str.upper().isin(['PENDING ACTIVITY', 'PENDING', 'FCASH', 'CASH'])]

        # Map Account Name to standard portfolio categories
        def map_account_name(name: str) -> str:
            if 'Stocks' in name:
                return 'Stocks'
            if 'Dividends' in name:
                return 'Dividends'
            if 'ETFs' in name:
                return 'ETFs'
            if 'International' in name:
                return 'International'
            if 'Shorts' in name:
                return 'Shorts'
            return name

        fidelity_df['Account Name'] = fidelity_df['Account Name'].astype(str).apply(map_account_name)

        # Clean numeric columns
        for col in ['Current Value', 'Cost Basis Total', 'Average Cost Basis', 'Last Price']:
            if col in fidelity_df.columns:
                fidelity_df[col] = fidelity_df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
                fidelity_df[col] = pd.to_numeric(fidelity_df[col], errors='coerce')

        # Group by Account Name and Symbol to preserve holdings per account
        agg_df = fidelity_df.groupby(['Account Name', 'Symbol']).agg({
            'Quantity': 'sum',
            'Current Value': 'sum',
            'Cost Basis Total': 'sum',
            'Last Price': 'first',
            'Average Cost Basis': 'mean',
        }).reset_index()

        agg_df.rename(columns={
            'Account Name': 'Account name',
            'Current Value': 'Current value',
            'Cost Basis Total': 'Cost basis total',
        }, inplace=True)

        return agg_df

    except Exception as e:
        print(f"Notice: Loading from Fidelity CSV failed or not found ({e}). Trying SQLite fallback...", file=sys.stderr)
        init_sqlite_db()
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM fidelity_positions")
            count = cursor.fetchone()[0]

            if count > 0:
                df = pd.read_sql_query("""
                    SELECT symbol as Symbol,
                           account_name as "Account name",
                           current_value as "Current value",
                           cost_basis_total as "Cost basis total"
                    FROM fidelity_positions
                    WHERE date = (SELECT MAX(date) FROM fidelity_positions)
                """, conn)

                # Filter out cash, sweep, and pending entries
                df = df[~df['Symbol'].str.endswith('**')]
                df = df[~df['Symbol'].str.upper().isin(['PENDING ACTIVITY', 'PENDING', 'FCASH', 'CASH'])]

                # Map account names to standard portfolio names
                df['Account name'] = df['Account name'].replace(['X Stocks', 'Stocks'], 'Stocks')
                df['Account name'] = df['Account name'].replace(['Z Dividends', 'Dividends'], 'Dividends')
                df['Account name'] = df['Account name'].replace(['Z ETFs', 'ETFs Roth'], 'ETFs')
                df['Account name'] = df['Account name'].replace(['Z Shorts', 'Shorts'], 'Shorts')
                df['Account name'] = df['Account name'].replace(['International'], 'International')
                return df
        raise FileNotFoundError(f"Could not load Fidelity positions from CSV or SQLite: {e}")


def adjustments_update_fidelity_percentages(
    fidelity_df: pd.DataFrame,
    workbook_url: str = PORTFOLIO_ADJUSTMENTS_URL,
    portfolios: Optional[list] = None,
    gc: Optional[gspread.Client] = None
):
    """
    Calculates Current Value % and Current Return % for each portfolio
    and updates the corresponding worksheet in the Google Sheets workbook.
    """
    if gc is None:
        gc = get_gspread_client()

    if portfolios is None:
        portfolios = PORTFOLIOS

    for portfolio in portfolios:
        if portfolio not in DCT_ADJUSTMENT_ID:
            print(f"Skipping unknown portfolio '{portfolio}' (no sheet ID defined)")
            continue

        print(f"Processing portfolio: {portfolio}")
        df = fidelity_df[fidelity_df['Account name'] == portfolio].copy()
        if df.empty:
            print(f"\tNo holdings found for portfolio '{portfolio}'. Skipping.")
            continue

        df = df[['Symbol', 'Current value', 'Cost basis total']]
        current_total = round(sum(df['Current value']), 2)
        cost_basis_total = round(sum(df['Cost basis total']), 2)

        df['Current value %'] = (df['Current value'] / current_total)
        df['Current return %'] = ((df['Current value'] - df['Cost basis total']) / df['Cost basis total'])
        df_update = df[['Symbol', 'Current value %', 'Current return %']].copy()

        worksheet_id = DCT_ADJUSTMENT_ID[portfolio]
        # Replace Infinity with NaN, then replace all NaNs with an empty string
        df_update = df_update.replace([np.inf, -np.inf], np.nan)
        df_update = df_update.fillna('')

        worksheet_update_with_df(gc, workbook_url, worksheet_id, df_update)


def main():
    parser = argparse.ArgumentParser(description="Update Portfolio Adjustments Google Sheets with Fidelity percentages.")
    parser.add_argument("--file", default=None, help="Path to specific Fidelity Portfolio_Positions CSV file.")
    parser.add_argument("--skip-sheets", action="store_true", help="Calculate percentages without pushing to Google Sheets (dry run).")
    args = parser.parse_args()

    date_str, raw_fidelity_df = df_fidelity_positions_portfolio(args.file)
    print(f"Found Fidelity Positions export for date: {date_str}")

    fidelity_df = df_fidelity_portfolios(args.file)
    print(f"Loaded {len(fidelity_df)} portfolio position records.")

    if args.skip_sheets:
        for portfolio in PORTFOLIOS:
            df = fidelity_df[fidelity_df['Account name'] == portfolio].copy()
            if df.empty:
                continue
            cur_tot = round(sum(df['Current value']), 2)
            cb_tot = round(sum(df['Cost basis total']), 2)
            df['Current value %'] = (df['Current value'] / cur_tot)
            df['Current return %'] = ((df['Current value'] - df['Cost basis total']) / df['Cost basis total'])
            print(f"\n--- {portfolio} (Holdings: {len(df)}, Total: ${cur_tot:,.2f}, Cost: ${cb_tot:,.2f}) ---")
            print(df[['Symbol', 'Current value %', 'Current return %']].head())

        print("\n--- Fidelity Positions Worksheet (All Tickers Aggregated) ---")
        summary_df = df_clean_fidelity_for_worksheet(raw_fidelity_df)
        print(summary_df.head(10))
    else:
        gc = get_gspread_client()
        # 1. Update individual portfolio tabs (Dividends, ETFs, International, Shorts, Stocks)
        adjustments_update_fidelity_percentages(fidelity_df, workbook_url=PORTFOLIO_ADJUSTMENTS_URL, gc=gc)
        # 2. Update 'Fidelity Positions' tab with all aggregated tickers from the CSV
        update_fidelity_positions_worksheet(raw_fidelity_df, workbook_url=PORTFOLIO_ADJUSTMENTS_URL, gc=gc)
        print("\nSuccessfully updated Google Sheets Portfolio Adjustments.")


if __name__ == "__main__":
    main()