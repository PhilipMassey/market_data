import os
import sys

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.ticker_reader import get_tickers, get_tickers_from_directory

# Folder names in tickers/
HOLDING_DIR = 'Holding'
SA_DIR = 'Seeking_Alpha'

# Portfolio categories
portfolios = ['Dividends', 'ETFs', 'International', 'Stocks']

if __name__ == '__main__':
    current_symbols = []
    for port in portfolios:
        current_symbols.extend(get_tickers(HOLDING_DIR, 'Current ' + port))
    current_symbols.extend(get_tickers(HOLDING_DIR, 'Current Others'))
    current_symbols = set(current_symbols)

    all_holding_symbols = set(get_tickers_from_directory(HOLDING_DIR))

    print('Current symbols count:', len(current_symbols))
    print('All Holding symbols count:', len(all_holding_symbols))
    print('Holding extras (in Holding but not in Current):', all_holding_symbols.difference(current_symbols))
    print('Current extras (in Current but not in Holding):', current_symbols.difference(all_holding_symbols))