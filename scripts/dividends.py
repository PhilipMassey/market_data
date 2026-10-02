# Download dividends transaction to csv files in directory 'Cloud Drive/investing/dividends/dividends year'
# Change the year In the Google 'Dividend' work book
# Add a new year sheet and add id to 'dct_dividends_worksheet_id'
# Create the pivot table with 3 columns, one for Symbol , one for Quarter, one for Dividend
import os
from os.path import join, isfile
from os import listdir
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe

SERVICE_ACCOUNT_FILE = '/Users/philipmassey/.config/gspread/service_account.json'
try:
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
except Exception:
    gc = None

dividends_dir = '/Users/philipmassey/Library/Mobile Documents/com~apple~CloudDocs/investing/dividends/'
workbook_name = 'Dividends'
dct_dividends_worksheet_id = {'2024': 1040963489, '2025': 1563512834, '2026': 282663853}


def df_sum_symbol_div_amount(quarter, year, file_path=None):
    """
    Reads dividend transactions for a quarter and aggregates/sums dividends by symbol.
    """
    if file_path is None:
        base_path = globals().get('path', join(dividends_dir, 'dividends ' + str(year)))
        file_path = join(base_path, 'Accounts_History Q{}.csv'.format(quarter))
    df = pd.read_csv(file_path)
    df = df.dropna(subset=['Symbol', 'Amount ($)'])
    df['Dividend'] = df['Amount ($)']
    df = df.groupby('Symbol').agg({'Dividend': 'sum'})
    df.reset_index(inplace=True)
    df['Quarter'] = '{} {}'.format(quarter, year)
    return df[['Quarter', 'Symbol', 'Dividend']]


def df_ungroup_symbol_div_amount(quarter, year, file_path=None):
    """
    Reads dividend transactions for a quarter without grouping by symbol,
    including the transaction date after the dividend amount.
    """
    if file_path is None:
        base_path = globals().get('path', join(dividends_dir, 'dividends ' + str(year)))
        file_path = join(base_path, 'Accounts_History Q{}.csv'.format(quarter))
    df = pd.read_csv(file_path)
    df = df.dropna(subset=['Symbol', 'Amount ($)'])
    df['Dividend'] = df['Amount ($)']
    df['Quarter'] = '{} {}'.format(quarter, year)

    # Detect Date column (Run Date, Date, Settlement Date, etc.)
    date_col = next((c for c in ['Run Date', 'Date', 'Transaction Date', 'Settlement Date'] if c in df.columns), None)
    if date_col:
        df['Date'] = df[date_col]
    elif 'Date' not in df.columns:
        df['Date'] = ''

    res_df = df[['Quarter', 'Symbol', 'Dividend', 'Date']].copy()
    if not res_df.empty:
        res_df = res_df.sort_values(
            by='Date', key=lambda col: pd.to_datetime(col, errors='coerce'), ascending=False
        ).reset_index(drop=True)
    return res_df


def worksheet_update_with_df(workbook_name, worksheet_id, df, row=1, col=1, client=None):
    """
    Updates the worksheet with a DataFrame starting from row and col (default: A1).
    """
    c = client or gc
    if c is None:
        c = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    workbook = c.open(workbook_name)
    worksheet = workbook.get_worksheet_by_id(worksheet_id)
    return set_with_dataframe(worksheet, df, row=row, col=col, include_index=False, include_column_header=True)


def worksheet_insert_ungrouped_with_df(workbook_name, worksheet_id, df, row=1, col=5, client=None):
    """
    Inserts ungrouped dividends DataFrame into the spreadsheet starting from row 1, column E (col=5).
    """
    return worksheet_update_with_df(workbook_name, worksheet_id, df, row=row, col=col, client=client)


if __name__ == '__main__':
    year = '2026'
    path = join(dividends_dir, 'dividends ' + year)
    worksheet_id = dct_dividends_worksheet_id[year]

    df_all = pd.DataFrame({})
    df_ungrouped_all = pd.DataFrame({})
    for q in range(1, 4):
        df = df_sum_symbol_div_amount(q, year)
        df_all = pd.concat([df_all, df])

        df_ungrouped = df_ungroup_symbol_div_amount(q, year)
        df_ungrouped_all = pd.concat([df_ungrouped_all, df_ungrouped])

    # Sort entire ungrouped dataset descending by date across all quarters
    if not df_ungrouped_all.empty and 'Date' in df_ungrouped_all.columns:
        df_ungrouped_all = df_ungrouped_all.sort_values(
            by='Date', key=lambda col: pd.to_datetime(col, errors='coerce'), ascending=True
        ).reset_index(drop=True)

    # print(df_all.head())
    # worksheet_update_with_df(workbook_name, worksheet_id, df_all, row=1, col=1)
    # print("--- Inserted Grouped Dividends (Columns A-C) ---")
    
    print(df_ungrouped_all.head())
    worksheet_insert_ungrouped_with_df(workbook_name, worksheet_id, df_ungrouped_all, row=1, col=5)
    print("--- Inserted Ungrouped Dividends (Columns E-H) ---")
