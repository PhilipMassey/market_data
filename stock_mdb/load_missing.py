import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stock_mdb.market_data_close import download_and_insert_missing_close_prices

def find_and_load_missing_close_prices():
    """
    Finds and loads missing close prices in the SQLite database by calling
    the daily maintenance procedure in market_data_close.py.
    """
    download_and_insert_missing_close_prices()

if __name__ == "__main__":
    find_and_load_missing_close_prices()
