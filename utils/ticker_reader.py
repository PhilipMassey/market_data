import os
import glob
import pandas as pd
from typing import List

# --- Configuration ---
# Define the root directory where your portfolio data folders are stored.
# os.path.expanduser('~/Documents') is a good default that points to your user's Documents folder.
PROJECT_ROOT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS_ROOT_DIRECTORY = os.path.join(PROJECT_ROOT_DIRECTORY, 'tickers')

def get_tickers_from_directory(folder_name: str) -> List[str]:
    """
    Reads all simple, single-column CSV files in a directory under the 'tickers' folder.
    Used for lists of tickers (e.g., from Seeking Alpha, ETFs).
    If 'ALL_FOLDERS' is passed, it scans all subdirectories.

    Args:
        folder_name: The name of the subdirectory (e.g., 'ETF', 'Holding', 'Seeking_Alpha') or 'ALL_FOLDERS'.

    Returns:
        A list of unique ticker strings.
    """
    master_set = set()

    if folder_name == 'ALL_FOLDERS':
        # Get all subdirectories in the tickers root
        if not os.path.exists(TICKERS_ROOT_DIRECTORY):
            return []
            
        subdirectories = [d for d in os.listdir(TICKERS_ROOT_DIRECTORY) 
                          if os.path.isdir(os.path.join(TICKERS_ROOT_DIRECTORY, d))]
        for subdir in subdirectories:
            # Recursively call this function for each subdirectory and update the set
            master_set.update(get_tickers_from_directory(subdir))
        return sorted(list(master_set))

    # --- Logic for a single directory ---
    target_dir = os.path.join(TICKERS_ROOT_DIRECTORY, folder_name)
    
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        return []

    csv_files = glob.glob(os.path.join(target_dir, "*.csv"))

    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path, header=None)
            if not df.empty:
                tickers = df[0].dropna().astype(str).str.strip().str.upper().tolist()
                
                # Clean up headers that might have been interpreted as tickers
                if 'SYMBOL' in tickers:
                    tickers.remove('SYMBOL')
                if 'TICKER' in tickers:
                    tickers.remove('TICKER')
                    
                master_set.update(tickers)
        except Exception as e:
            print(f"Error reading simple ticker list {file_path}: {e}")

    return sorted(list(master_set))

def get_tickers_from_portfolio(folder_name: str, portfolio_prefix: str) -> List[str]:
    """
    Reads the latest portfolio CSV file matching a prefix from a specified folder
    and extracts tickers from the 'Symbol' column.

    Args:
        folder_name: The name of the folder inside DATA_ROOT_DIRECTORY.
        portfolio_prefix: The prefix of the filename to search for (e.g., 'Portfolio_Positions').

    Returns:
        A list of unique ticker strings from the portfolio.
    """
    full_folder_path = os.path.join(TICKERS_ROOT_DIRECTORY, folder_name)
    
    if not os.path.exists(full_folder_path):
        print(f"Portfolio directory not found: {full_folder_path}")
        return []

    # Find the latest portfolio file matching the prefix
    search_pattern = os.path.join(full_folder_path, f"{portfolio_prefix}*.csv")
    all_files = glob.glob(search_pattern)
    
    if not all_files:
        print(f"No '{portfolio_prefix}*.csv' files found in {full_folder_path}")
        return []

    latest_file = max(all_files, key=os.path.getctime)
    
    all_tickers = set()
    
    try:
        df = pd.read_csv(latest_file)
        
        if 'Symbol' in df.columns:
            tickers = df['Symbol'].dropna().astype(str).str.strip().str.upper().tolist()
            #excluded_symbols = ['FDRXX', 'SPAXX', 'CORE**']
            #tickers = [t for t in tickers if t and t not in excluded_symbols]
            
            # Additional cleanup just in case
            if 'SYMBOL' in tickers:
                 tickers.remove('SYMBOL')

            all_tickers.update(tickers)
        else:
            print(f"Warning: 'Symbol' column not found in {latest_file}.")

    except Exception as e:
        print(f"Error reading portfolio {latest_file}: {e}")

    return sorted(list(all_tickers))

def get_tickers(folder: str, portfolio: str = None) -> List[str]:
    """
    Primary router function to get tickers.
    - If only 'folder' is provided, gets tickers from that simple list directory.
    - If 'folder' and 'portfolio' are provided, gets tickers from that portfolio file.
    """
    if portfolio:
        return get_tickers_from_portfolio(folder, portfolio)
    else:
        return get_tickers_from_directory(folder)

def get_all_tickers() -> List[str]:
    """
    Aggregates and deduplicates tickers from ALL configured sources.
    """
    master_set = set()
    
    # Get tickers from all simple list directories
    master_set.update(get_tickers_from_directory('ALL_FOLDERS'))
    
    return sorted(list(master_set))

if __name__ == "__main__":
    # --- Example for simple ticker lists ---
    #etf_tickers = get_tickers_from_directory('Holding')
    #print("ETF Tickers:", etf_tickers)
    folder = 'ALL_FOLDERS'
    tickers = get_tickers(folder)
    print(folder ,"Tickers:",len(tickers), tickers )
    # --- Example for portfolio ---
    # This will now look in a path like '/Users/your_user/Documents/Fidelity_Exports'
    # portfolio_tickers = get_tickers_from_portfolio('Fidelity_Exports', 'Portfolio_Positions')
    # print("Portfolio Tickers:", portfolio_tickers)
    pass
