import os
import glob
import sys
import re
import math
from datetime import datetime
import pandas as pd
import numpy as np

# Ensure project root is in path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def extract_date_from_filename(file_path: str) -> str:
    """
    Extracts date from filename like Portfolio_Positions_Jun-07-2026.csv
    Returns date string in YYYY-MM-DD format.
    """
    basename = os.path.basename(file_path)
    # Match the date portion, e.g., Jun-07-2026
    match = re.search(r'Portfolio_Positions_([A-Za-z]{3}-\d{2}-\d{4})\.csv', basename)
    if not match:
        raise ValueError(f"Filename does not match expected format Portfolio_Positions_Month-Day-Year.csv: {basename}")
    
    date_str = match.group(1)
    try:
        dt = datetime.strptime(date_str, "%b-%d-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Could not parse date '{date_str}' from filename: {e}")

def df_fidelity_positions_aggregate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the CSV dataframe and aggregates rows by Symbol.
    """
    # 1. Filter out rows where Symbol is null/empty
    df = df.dropna(subset=['Symbol'])
    df['Symbol'] = df['Symbol'].astype(str).str.strip()
    df = df[df['Symbol'] != '']

    # 2. Clean dollar and percentage columns
    dollar_cols = ['Current Value', 'Cost Basis Total', 'Average Cost Basis', 'Last Price']
    for col in dollar_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    percent_cols = ['Percent Of Account']
    for col in percent_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Quantity' in df.columns:
        df['Quantity'] = df['Quantity'].astype(str).str.replace(',', '', regex=False).str.strip()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')

    if 'Account Name' in df.columns:
        df['Account Name'] = df['Account Name'].astype(str).str.strip()
    else:
        df['Account Name'] = 'Unknown'

    # 3. Aggregate columns on symbol
    agg_df = df.groupby('Symbol').agg({
        'Account Name': 'first',
        'Quantity': 'sum',
        'Current Value': 'sum',
        'Cost Basis Total': 'sum',
        'Last Price': 'first',
        'Average Cost Basis': 'mean',
        'Percent Of Account': 'mean'
    })
    agg_df.reset_index(inplace=True)
    agg_df = agg_df.rename(columns={'index': 'Symbol'})
    return agg_df

def _read_xlsx_data_only(file_path: str) -> pd.DataFrame:
    """
    Read cell values from an xlsx file by parsing the zip/XML directly.
    This bypasses openpyxl's conditional formatting parser which crashes on
    Seeking Alpha exports with unsupported filter operators.
    """
    import zipfile
    from xml.etree import ElementTree
    
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    
    with zipfile.ZipFile(file_path) as z:
        # Read shared strings table
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ElementTree.parse(z.open('xl/sharedStrings.xml'))
            for si in tree.iter(f'{{{ns}}}si'):
                t = si.find(f'.//{{{ns}}}t')
                shared_strings.append(t.text if t is not None and t.text else '')
        
        # Read first sheet data
        tree = ElementTree.parse(z.open('xl/worksheets/sheet1.xml'))
        
        rows = []
        for row_elem in tree.iter(f'{{{ns}}}row'):
            row_data = []
            for cell in row_elem.findall(f'{{{ns}}}c'):
                cell_type = cell.get('t', '')
                val_elem = cell.find(f'{{{ns}}}v')
                if cell_type == 'inlineStr':
                    # Inline string: value is in <is><t>text</t></is>
                    is_elem = cell.find(f'{{{ns}}}is')
                    if is_elem is not None:
                        t = is_elem.find(f'{{{ns}}}t')
                        row_data.append(t.text if t is not None and t.text else '')
                    else:
                        row_data.append('')
                elif val_elem is not None and val_elem.text:
                    if cell_type == 's':  # shared string reference
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
    
    # Pad rows to same length as header
    n_cols = len(rows[0])
    for i in range(1, len(rows)):
        while len(rows[i]) < n_cols:
            rows[i].append('')
    
    return pd.DataFrame(rows[1:], columns=rows[0])

def process_seeking_alpha_exports() -> bool:
    """
    Scans ~/Downloads for Seeking Alpha Excel files (* YYYY-MM-DD.xlsx).
    Finds the latest file for each base name, extracts ticker symbols from the
    'Symbol' column, and writes them to tickers/Seeking_Alpha/<Base Name>.csv.
    Returns True if all processed files succeeded, False if any failed.
    """
    downloads_dir = os.path.expanduser('~/Downloads')
    search_pattern = os.path.join(downloads_dir, '*.xlsx')
    files = glob.glob(search_pattern)
    
    # Target directories
    sa_dir = os.path.join(project_root, 'tickers', 'Seeking_Alpha')
    holding_dir = os.path.join(project_root, 'tickers', 'Holding')
    
    # Parse filenames and group them by base name
    # e.g., 'Current Dividends 2026-06-14.xlsx' -> base_name='Current Dividends', date='2026-06-14'
    file_pattern = re.compile(r'^(.*?)\s+(\d{4}-\d{2}-\d{2})\.xlsx$')
    
    grouped_files = {}  # base_name -> [(date_str, file_path)]
    
    for f in files:
        basename = os.path.basename(f)
        match = file_pattern.match(basename)
        if match:
            base_name = match.group(1).strip()
            date_str = match.group(2)
            if base_name not in grouped_files:
                grouped_files[base_name] = []
            grouped_files[base_name].append((date_str, f))
            
    if not grouped_files:
        print("No Seeking Alpha Excel files (* YYYY-MM-DD.xlsx) found in ~/Downloads.")
        return True

    success = True
    for base_name, versions in grouped_files.items():
        # Find the version with the latest date
        # Since date format is YYYY-MM-DD, standard string sorting works correctly
        latest_version = max(versions, key=lambda x: x[0])
        latest_date, file_path = latest_version
        
        print(f"Processing Seeking Alpha export: {os.path.basename(file_path)} (latest version: {latest_date})")
        
        try:
            # Read xlsx directly as zip to bypass openpyxl conditional formatting parsing
            df = _read_xlsx_data_only(file_path)
            if df.empty:
                print(f"Warning: Seeking Alpha export '{os.path.basename(file_path)}' has no data rows. Skipping.", file=sys.stderr)
                success = False
                continue
            
            if 'Symbol' not in df.columns:
                print(f"Warning: 'Symbol' column not found in Seeking Alpha export '{os.path.basename(file_path)}'. Skipping.", file=sys.stderr)
                success = False
                continue
                
            # Clean and get symbols: drop NaNs, strip spaces, convert to uppercase, drop duplicates
            symbols = df['Symbol'].dropna().astype(str).str.strip().str.upper()
            symbols = symbols[symbols != ''].drop_duplicates().tolist()
            
            # Sort alphabetically
            symbols.sort()
            
            # Determine target directory: if base name starts with 'Current ', write to tickers/Holding
            if base_name.startswith("Current "):
                dest_dir = holding_dir
            else:
                dest_dir = sa_dir
            
            # Write to CSV
            os.makedirs(dest_dir, exist_ok=True)
            output_csv_path = os.path.join(dest_dir, f"{base_name}.csv")
            out_df = pd.DataFrame({'Symbol': symbols})
            out_df.to_csv(output_csv_path, index=False)
            
            print(f"Successfully wrote {len(symbols)} symbols to {output_csv_path}")
            
        except Exception as e:
            print(f"Warning: Error processing Seeking Alpha export '{os.path.basename(file_path)}': {e}", file=sys.stderr)
            success = False
            
    return success

def write_fidelity_accounts_to_csv(df: pd.DataFrame, project_root: str):
    """
    Groups the Fidelity export DataFrame by 'Account Name', excludes cash/core
    symbols, and writes each account's symbols to tickers/Holding/<Account Name>.csv.
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    # 1. Ensure Symbol and Account Name columns exist
    if 'Symbol' not in df.columns:
        print("Warning: 'Symbol' column not found in Fidelity export for writing account CSVs.", file=sys.stderr)
        return
        
    if 'Account Name' not in df.columns:
        df['Account Name'] = 'Unknown'
        
    # Clean Symbol and Account Name
    df = df.dropna(subset=['Symbol'])
    df['Symbol'] = df['Symbol'].astype(str).str.strip()
    df['Account Name'] = df['Account Name'].fillna('Unknown').astype(str).str.strip()
    
    # Filter out empty entries
    df = df[(df['Symbol'] != '') & (df['Account Name'] != '')]
    
    # 2. Exclude cash/core symbols
    def is_cash_or_core(symbol: str) -> bool:
        sym = symbol.upper()
        if sym.endswith('**'):
            return True
        if sym in ('FCASH', 'CASH', 'PENDING ACTIVITY', 'PENDING'):
            return True
        return False
        
    df = df[~df['Symbol'].apply(is_cash_or_core)]
    
    # 3. Map Account Name to rolled-up categories
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
        
    df['Mapped Account Name'] = df['Account Name'].apply(map_account_name)
    
    # 4. Write each group to tickers/Holding/<Mapped Account Name>.csv
    holding_dir = os.path.join(project_root, 'tickers', 'Holding')
    os.makedirs(holding_dir, exist_ok=True)
    
    grouped = df.groupby('Mapped Account Name')
    for account_name, group in grouped:
        if not account_name:
            continue
            
        # Get unique, uppercase symbols, sorted alphabetically
        symbols = group['Symbol'].str.upper().drop_duplicates().tolist()
        symbols.sort()
        
        output_path = os.path.join(holding_dir, f"{account_name}.csv")
        out_df = pd.DataFrame({'Symbol': symbols})
        out_df.to_csv(output_path, index=False)
        print(f"Successfully wrote {len(symbols)} symbols from Fidelity account '{account_name}' to {output_path}")

def process_fidelity_export(file_path: str):
    """
    Parses the downloaded Portfolio_Positions[...].csv (exported from Fidelity Investments),
    aggregates the current holdings, tags them with the export date, and inserts
    the data row-by-row into the SQLite fidelity_positions table.
    """
    print(f"Processing Fidelity export from: {file_path}")
    
    # 1. Parse Date from file name
    date_str = extract_date_from_filename(file_path)
    print(f"Parsed Date: {date_str}")
        
    # 2. Read CSV with index_col=False
    try:
        df = pd.read_csv(file_path, index_col=False, encoding='utf-8-sig')
    except Exception as e:
        raise RuntimeError(f"Error reading CSV file '{file_path}': {e}")
    
    # 3. Normalize column names (Fidelity changed from Title Case to lowercase)
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
        
    # Write the account-specific CSVs to tickers/Holding/
    try:
        write_fidelity_accounts_to_csv(df, project_root)
    except Exception as e:
        print(f"Warning: Failed to write account CSVs from Fidelity export: {e}", file=sys.stderr)
        
    # 3. Clean and aggregate
    agg_df = df_fidelity_positions_aggregate_columns(df)
    
    # 4. Initialize SQLite DB
    init_sqlite_db()
    
    # 5. Prepare rows for insertion
    rows_to_insert = []
    for _, row in agg_df.iterrows():
        qty = None if pd.isna(row['Quantity']) else float(row['Quantity'])
        avg_cost = None if pd.isna(row['Average Cost Basis']) else float(row['Average Cost Basis'])
        total_cost = None if pd.isna(row['Cost Basis Total']) else float(row['Cost Basis Total'])
        curr_val = None if pd.isna(row['Current Value']) else float(row['Current Value'])
        acc_name = str(row['Account Name']) if not pd.isna(row['Account Name']) else None
        last_price = None if pd.isna(row['Last Price']) else float(row['Last Price'])
        pct_acct = None if pd.isna(row['Percent Of Account']) else float(row['Percent Of Account'])
        symbol = str(row['Symbol'])
        
        rows_to_insert.append((
            date_str,
            symbol,
            qty,
            avg_cost,
            total_cost,
            curr_val,
            acc_name,
            last_price,
            pct_acct
        ))
        
    # 6. Clear existing positions and insert new rows in SQLite DB
    try:
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fidelity_positions")
            cursor.executemany("""
                INSERT OR REPLACE INTO fidelity_positions (
                    date,
                    symbol,
                    quantity,
                    average_cost_basis,
                    cost_basis_total,
                    current_value,
                    account_name,
                    last_price,
                    percent_of_account
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows_to_insert)
        print(f"Successfully inserted {len(rows_to_insert)} records into SQLite fidelity_positions table for date {date_str}.")
    except Exception as e:
        raise RuntimeError(f"Error inserting into SQLite: {e}")

def compare_holdings_and_write_mismatches(project_root: str):
    """
    Compares 'Current <Category>.csv' with '<Category>.csv' inside tickers/Holding.
    Prints tickers only in Current (not in Holding) and only in Holding (not in Current).
    """
    holding_dir = os.path.join(project_root, 'tickers', 'Holding')
    if not os.path.exists(holding_dir):
        print(f"Holding directory not found: {holding_dir}")
        return
        
    def read_symbols(path: str) -> set:
        try:
            df = pd.read_csv(path)
            if 'Symbol' in df.columns:
                return set(df['Symbol'].dropna().astype(str).str.strip().str.upper())
        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)
        return set()

    current_files = glob.glob(os.path.join(holding_dir, 'Current *.csv'))
    mismatch_found = False
    
    for current_file in sorted(current_files):
        base = os.path.basename(current_file)
        category = base[len('Current '):]
        category_name = os.path.splitext(category)[0]
        target_file = os.path.join(holding_dir, category)
        
        if not os.path.exists(target_file):
            continue
            
        current_symbols = read_symbols(current_file)
        holding_symbols = read_symbols(target_file)
        
        in_current_not_holding = sorted(current_symbols - holding_symbols)
        in_holding_not_current = sorted(holding_symbols - current_symbols)
        
        if in_current_not_holding or in_holding_not_current:
            mismatch_found = True
            print(f"\n{category_name}:")
            if in_current_not_holding:
                print(f"  In Current but not Holding ({len(in_current_not_holding)}): {', '.join(in_current_not_holding)}")
            if in_holding_not_current:
                print(f"  In Holding but not Current ({len(in_holding_not_current)}): {', '.join(in_holding_not_current)}")
            
    if not mismatch_found:
        print("All categories match. No differences found.")

def update_holding_portfolios_from_file():
    """
    Scans ~/Downloads for Seeking Alpha Excel files and processes them.
    Scans ~/Downloads for exactly one Portfolio_Positions_*.csv file, and parses it.
    Exits with code 1 if either process failed.
    """
    overall_success = True

    # 1. Process Seeking Alpha Excel exports
    try:
        sa_success = process_seeking_alpha_exports()
        if not sa_success:
            overall_success = False
    except Exception as e:
        print(f"Error running Seeking Alpha processing: {e}", file=sys.stderr)
        overall_success = False

    # 2. Process Fidelity Positions export
    downloads_dir = os.path.expanduser('~/Downloads')
    search_pattern = os.path.join(downloads_dir, 'Portfolio_Positions_*.csv')
    files = glob.glob(search_pattern)
    
    fidelity_success = True
    if len(files) == 0:
        print("Error: No Portfolio_Positions_*.csv files found in ~/Downloads", file=sys.stderr)
        fidelity_success = False
    elif len(files) > 1:
        print(f"Error: Found multiple Portfolio_Positions_*.csv files in ~/Downloads. Expected exactly one.\nFiles found: {files}", file=sys.stderr)
        fidelity_success = False
    else:
        try:
            process_fidelity_export(files[0])
        except Exception as e:
            print(f"Error processing Fidelity export: {e}", file=sys.stderr)
            fidelity_success = False

    if not fidelity_success:
        overall_success = False

    # 3. Compare holdings and write mismatches
    try:
        compare_holdings_and_write_mismatches(project_root)
    except Exception as e:
        print(f"Error comparing holdings: {e}", file=sys.stderr)

    if not overall_success:
        sys.exit(1)

run = update_holding_portfolios_from_file
