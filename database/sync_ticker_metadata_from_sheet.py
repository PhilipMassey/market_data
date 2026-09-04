import os
import sys
import csv
import io
import urllib.request
import argparse
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from portfolio.ticker_period_ranks_data import clear_cache

import re

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1m7e7jdBkC3H4EUqE9LF-ZwQIy5ru5cuC2WLzu3_Y89A/export?format=csv&gid=106245017"


def normalize_sheet_url(url_or_path: str) -> str:
    """
    Normalizes a Google Sheets URL to its direct CSV export endpoint.
    Extracts spreadsheet ID and gid (sheet tab ID) if present.
    If given a local file path or already-formatted export URL, returns it properly.
    """
    if "docs.google.com/spreadsheets" in url_or_path:
        # Extract gid if present
        gid_match = re.search(r"gid=(\d+)", url_or_path)
        gid = gid_match.group(1) if gid_match else None

        if "/export?" not in url_or_path:
            parts = url_or_path.split("/d/")
            if len(parts) > 1:
                sheet_id = parts[1].split("/")[0].split("?")[0]
                export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                if gid:
                    export_url += f"&gid={gid}"
                return export_url
        elif gid and "gid=" not in url_or_path.split("/export?")[1]:
            return f"{url_or_path}&gid={gid}"
            
    return url_or_path


def fetch_csv_content(url_or_path: str) -> str:
    """
    Fetches raw CSV text from a remote URL or local file path.
    """
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        req = urllib.request.Request(
            url_or_path,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MarketDataSync/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8")
    else:
        with open(url_or_path, "r", encoding="utf-8") as f:
            return f.read()


def parse_sheet_csv(csv_text: str) -> List[Dict[str, str]]:
    """
    Parses CSV text into a list of ticker metadata dictionaries:
    [{'ticker': 'AAPL', 'sector': 'Technology', 'industry': 'Consumer Electronics'}, ...]
    """
    records = []
    ignored_tickers = {
        'TICKER', 'SYMBOL', 'SECTOR', 'INDUSTRY',
        'FDIC-INSURED DEPOSIT SWEEP', 'PENDING ACTIVITY', 'FCASH', 'CASH', 'PENDING'
    }

    reader = csv.reader(io.StringIO(csv_text))
    for row_idx, row in enumerate(reader):
        if not row or len(row) < 3:
            continue

        ticker = row[0].strip().upper()
        sector = row[1].strip()
        industry = row[2].strip()

        # Skip empty tickers or header rows
        if not ticker or ticker in ignored_tickers or ticker.endswith('**'):
            continue

        records.append({
            'ticker': ticker,
            'sector': sector or 'Unknown',
            'industry': industry or 'Unknown'
        })

    return records


def sync_ticker_metadata_from_sheet(sheet_url_or_path: str = DEFAULT_SHEET_URL) -> Dict[str, any]:
    """
    Synchronizes ticker sectors and industries from a Google Sheet into SQLite.
    Updates existing records or inserts new records, then invalidates ranking cache.
    """
    init_sqlite_db()
    
    url = normalize_sheet_url(sheet_url_or_path)
    print(f"Fetching metadata updates from: {url}")
    
    csv_text = fetch_csv_content(url)
    records = parse_sheet_csv(csv_text)
    
    if not records:
        print("No valid ticker records found in the sheet.")
        return {'total': 0, 'updated': 0, 'inserted': 0, 'tickers': []}

    updated_count = 0
    inserted_count = 0
    changed_tickers = []

    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        
        # Get existing tickers and their current metadata
        cursor.execute("SELECT ticker, sector, industry FROM ticker_meta_profile")
        existing_meta = {row[0].upper(): (row[1], row[2]) for row in cursor.fetchall()}

        for rec in records:
            ticker = rec['ticker']
            new_sector = rec['sector']
            new_industry = rec['industry']

            if ticker in existing_meta:
                curr_sector, curr_industry = existing_meta[ticker]
                if curr_sector != new_sector or curr_industry != new_industry:
                    cursor.execute("""
                        UPDATE ticker_meta_profile
                        SET sector = ?, industry = ?
                        WHERE ticker = ?
                    """, (new_sector, new_industry, ticker))
                    updated_count += 1
                    changed_tickers.append(ticker)
                    print(f"  [UPDATED] {ticker}: ({curr_sector} -> {new_sector}, {curr_industry} -> {new_industry})")
            else:
                cursor.execute("""
                    INSERT INTO ticker_meta_profile (ticker, company_name, type, sector, industry)
                    VALUES (?, ?, ?, ?, ?)
                """, (ticker, ticker, 'EQUITY', new_sector, new_industry))
                inserted_count += 1
                changed_tickers.append(ticker)
                print(f"  [INSERTED] {ticker}: Sector='{new_sector}', Industry='{new_industry}'")

    # Invalidate ranking cache so dashboards reload new groupings
    clear_cache()

    print(f"\nSync complete: {len(records)} records processed ({updated_count} updated, {inserted_count} inserted). Cache cleared.")
    return {
        'total': len(records),
        'updated': updated_count,
        'inserted': inserted_count,
        'tickers': changed_tickers
    }


def main():
    parser = argparse.ArgumentParser(description="Sync ticker sector & industry metadata from Google Sheet into SQLite.")
    parser.add_argument(
        "--url",
        default=DEFAULT_SHEET_URL,
        help="Google Sheet URL or local CSV file path (defaults to configured sheet)"
    )
    args = parser.parse_args()

    try:
        sync_ticker_metadata_from_sheet(args.url)
    except Exception as e:
        print(f"Error syncing metadata: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
