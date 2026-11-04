import os
import sys

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from portfolio.holding_portfolios_update import (
    process_seeking_alpha_exports,
    compare_holdings_and_write_mismatches,
)
from database.update_ticker_metadata import update_ticker_metadata

if __name__ == "__main__":
    success = process_seeking_alpha_exports()
    #compare_holdings_and_write_mismatches()
    if not success:
        sys.exit(1)
    print("\nSeeking Alpha exports loaded.")
    update_ticker_metadata()

