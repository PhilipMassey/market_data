import os
import re
import glob
import zipfile
from datetime import datetime
from typing import Optional, Tuple, Iterable
from xml.etree import ElementTree
import pandas as pd

PORTFOLIOS = ['Dividends', 'ETFs', 'International', 'Shorts', 'Stocks']

FIDELITY_COLUMN_MAPPING = {
    'Account name': 'Account Name',
    'Account number': 'Account Number',
    'Current value': 'Current Value',
    'Cost basis total': 'Cost Basis Total',
    'Average cost basis': 'Average Cost Basis',
    'Last price': 'Last Price',
    'Percent of account': 'Percent Of Account',
}

CASH_SYMBOLS = (
    'FDIC-INSURED DEPOSIT SWEEP',
    'PENDING ACTIVITY',
    'FCASH',
    'CASH',
    'PENDING',
    'MONEY MARKET',
)

SERVICE_ACCOUNT_FILE = os.path.expanduser("~/.config/gspread/service_account.json")


def is_cash(symbol: str) -> bool:
    """Returns True if the symbol represents a cash, core sweep, or pending activity entry."""
    if not symbol or not isinstance(symbol, str):
        return False
    sym = symbol.strip().upper()
    return sym.endswith('**') or sym in CASH_SYMBOLS


def filter_out_cash_symbols(df: pd.DataFrame, symbol_col: str = 'Symbol') -> pd.DataFrame:
    """Filters out empty, NaN, and cash/core/pending symbols from a DataFrame."""
    if symbol_col not in df.columns:
        return df
    df = df.dropna(subset=[symbol_col]).copy()
    df[symbol_col] = df[symbol_col].astype(str).str.strip()
    df = df[df[symbol_col] != '']
    return df[~df[symbol_col].apply(is_cash)]


def map_account_name(name: str) -> str:
    """Maps raw Fidelity account names (e.g., 'Individual - Stocks', 'Z ETFs') to standard categories."""
    if not isinstance(name, str):
        return str(name)
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


def normalize_fidelity_columns(df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
    """Normalizes Fidelity CSV column names to standard Title Case."""
    if inplace:
        df.rename(columns=FIDELITY_COLUMN_MAPPING, inplace=True)
        return df
    return df.rename(columns=FIDELITY_COLUMN_MAPPING)


def clean_numeric_columns(
    df: pd.DataFrame,
    dollar_cols: Optional[Iterable[str]] = None,
    percent_cols: Optional[Iterable[str]] = None,
    numeric_cols: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Strips '$', '%', and ',' from specified columns and converts them to float."""
    if dollar_cols:
        for col in dollar_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace('$', '', regex=False)
                    .str.replace(',', '', regex=False)
                    .str.strip()
                )
                df[col] = pd.to_numeric(df[col], errors='coerce')

    if percent_cols:
        for col in percent_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace('%', '', regex=False)
                    .str.replace(',', '', regex=False)
                    .str.strip()
                )
                df[col] = pd.to_numeric(df[col], errors='coerce')

    if numeric_cols:
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def extract_date_from_filename(file_path: str) -> str:
    """
    Extracts date from filename like Portfolio_Positions_Jun-07-2026.csv
    Returns date string in YYYY-MM-DD format.
    """
    basename = os.path.basename(file_path)
    match = re.search(r'Portfolio_Positions_([A-Za-z]{3}-\d{2}-\d{4})\.csv', basename)
    if not match:
        raise ValueError(f"Filename does not match expected format Portfolio_Positions_Month-Day-Year.csv: {basename}")

    date_str = match.group(1)
    try:
        dt = datetime.strptime(date_str, "%b-%d-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Could not parse date '{date_str}' from filename: {e}")


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


def read_xlsx_data_only(file_path: str) -> pd.DataFrame:
    """
    Read cell values from an xlsx file by parsing the zip/XML directly.
    This bypasses openpyxl's conditional formatting parser which crashes on
    Seeking Alpha exports with unsupported filter operators.
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

    with zipfile.ZipFile(file_path) as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ElementTree.parse(z.open('xl/sharedStrings.xml'))
            for si in tree.iter(f'{{{ns}}}si'):
                t = si.find(f'.//{{{ns}}}t')
                shared_strings.append(t.text if t is not None and t.text else '')

        tree = ElementTree.parse(z.open('xl/worksheets/sheet1.xml'))

        rows = []
        for row_elem in tree.iter(f'{{{ns}}}row'):
            row_data = []
            for cell in row_elem.findall(f'{{{ns}}}c'):
                cell_type = cell.get('t', '')
                val_elem = cell.find(f'{{{ns}}}v')
                if cell_type == 'inlineStr':
                    is_elem = cell.find(f'{{{ns}}}is')
                    if is_elem is not None:
                        t = is_elem.find(f'{{{ns}}}t')
                        row_data.append(t.text if t is not None and t.text else '')
                    else:
                        row_data.append('')
                elif val_elem is not None and val_elem.text:
                    if cell_type == 's':
                        idx = int(val_elem.text)
                        row_data.append(shared_strings[idx] if idx < len(shared_strings) else '')
                    else:
                        row_data.append(val_elem.text)
                else:
                    row_data.append('')
            if row_data:
                rows.append(row_data)

    if len(rows) < 2:
        return pd.DataFrame()

    n_cols = len(rows[0])
    for i in range(1, len(rows)):
        while len(rows[i]) < n_cols:
            rows[i].append('')

    return pd.DataFrame(rows[1:], columns=rows[0])


_read_xlsx_data_only = read_xlsx_data_only


def get_gspread_client(credentials_file: str = SERVICE_ACCOUNT_FILE):
    """
    Initializes and returns a Google Sheets API client using service account credentials.
    """
    import gspread
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"Google service account file not found at: {credentials_file}")
    return gspread.service_account(filename=credentials_file)


def worksheet_update_with_df(
    gc,
    workbook_url: str,
    worksheet_id: int,
    df: pd.DataFrame,
    clear_range: str = "A1:Z69",
    set_df_fn=None,
):
    """
    Updates a specific Google Worksheet by ID with the given DataFrame.
    Preserves existing formatting and formulas at or below row 70 by clearing only A1:Z69.
    """
    if set_df_fn is None:
        from gspread_dataframe import set_with_dataframe
        set_df_fn = set_with_dataframe
    workbook = gc.open_by_url(workbook_url)
    worksheet = workbook.get_worksheet_by_id(worksheet_id)
    worksheet.batch_clear([clear_range])
    result = set_df_fn(worksheet, df, row=1, col=1, include_index=False, include_column_header=True)
    print(f"\tUpdated worksheet '{worksheet.title}' (ID {worksheet_id}) with {len(df)} rows.")
    return result

