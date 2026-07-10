from portfolio.holding_portfolios_update import update_holding_portfolios_from_file
from database.update_ticker_metadata import update_ticker_metadata

if __name__ == "__main__":
    update_holding_portfolios_from_file()
    print("\nPortfolios loaded. Checking for any unassigned tickers and updating metadata...")
    update_ticker_metadata()

