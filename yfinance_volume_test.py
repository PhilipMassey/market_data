import yfinance as yf
import pandas as pd
from utils.ticker_reader import get_tickers_from_directory

def download_volume():
    # Try to get real tickers first
    directories = ['ETF', 'Holding', 'Seeking_Alpha']
    all_tickers = set()
    for directory in directories:
        all_tickers.update(get_tickers_from_directory(directory))
    
    tickers = sorted(list(all_tickers))
    print(f"\nAttempting to download data for {len(tickers)} tickers at once...")
    print("Period: Past 5 days")
    print("-" * 50)

    try:
        # We use a 5-day period for a quick test
        data = yf.download(tickers, period="5d", progress=True)
        
        if data.empty:
            print("Download returned an empty DataFrame.")
            return

        close_prices = data['Close']
        
        # Check if any tickers completely failed
        failed_tickers = []
        for ticker in tickers:
            if ticker not in close_prices.columns:
                failed_tickers.append(ticker)
            elif close_prices[ticker].isna().all():
                failed_tickers.append(ticker)

        print("\n" + "-" * 50)
        print("DOWNLOAD RESULTS:")
        print("-" * 50)
        print(f"Total Requested: {len(tickers)}")
        print(f"Total Successfully Fetched: {len(tickers) - len(failed_tickers)}")
        
        if failed_tickers:
            print(f"\nFailed Tickers ({len(failed_tickers)}):")
            print(failed_tickers)
            print("\nNote: Some failures are normal (e.g., delisted tickers, wrong symbols, or yfinance rate limits).")
        else:
            print("\nAll tickers fetched successfully!")

    except Exception as e:
        print(f"\nAn error occurred during bulk download: {e}")
        print("This usually indicates a severe rate limit block or a connection issue.")

if __name__ == "__main__":
    download_volume()
