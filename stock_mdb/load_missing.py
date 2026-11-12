from stock_mdb.market_data_close import download_and_insert_missing_close_prices
from portfolio.ticker_period_ranks_data import clear_cache
from scripts.period_rank_filter import run_period_rank_filter
from utils.period_rank_utils import send_period_rank_email


def find_and_load_missing_close_prices():
    """
    Finds and loads missing close prices in the SQLite database by calling
    the daily maintenance procedure in market_data_close.py.
    """
    download_and_insert_missing_close_prices()
    clear_cache()


if __name__ == "__main__":
    find_and_load_missing_close_prices()
    print("\nRunning period rank filter...")
    run_period_rank_filter()
    send_period_rank_email()
