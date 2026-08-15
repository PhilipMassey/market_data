import os
import sys

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from utils.ticker_reader import get_all_tickers
from portfolio.ticker_period_ranks_data import clear_cache


def delete_orphan_profiles():
    """
    Deletes all records from 'ticker_meta_profile' whose tickers are NOT
    present in any CSV file in the 'tickers/' directory.
    """
    init_sqlite_db()
    
    # 1. Fetch valid tickers from all CSV files
    csv_tickers = {t.upper() for t in get_all_tickers() if t}
    print(f"Found {len(csv_tickers)} unique active tickers across CSV files.")
    
    if not csv_tickers:
        print("Warning: No tickers found in CSV files. Aborting deletion to prevent wiping table.")
        return 0

    # 2. Query all existing records in ticker_meta_profile
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, company_name, type, sector, industry FROM ticker_meta_profile")
        all_meta_records = cursor.fetchall()
        
        # 3. Identify orphan records
        orphan_records = [
            row for row in all_meta_records 
            if row[0].upper() not in csv_tickers
        ]
        
        if not orphan_records:
            print("Database is clean. All records in ticker_meta_profile correspond to active CSV tickers.")
            return 0
            
        print(f"\nFound {len(orphan_records)} orphan profile record(s) in 'ticker_meta_profile' not in CSV files:")
        for row in orphan_records[:30]:
            print(f"  - {row[0]}: Name='{row[1]}' | Type={row[2]} | Sector='{row[3]}' | Industry='{row[4]}'")
        if len(orphan_records) > 30:
            print(f"  ... and {len(orphan_records) - 30} more.")
            
        orphan_tickers = [row[0] for row in orphan_records]
        
        # 4. Delete orphan records in chunks of 500
        chunk_size = 500
        total_deleted = 0
        for i in range(0, len(orphan_tickers), chunk_size):
            chunk = orphan_tickers[i:i + chunk_size]
            placeholders = ', '.join(['?'] * len(chunk))
            delete_query = f"DELETE FROM ticker_meta_profile WHERE ticker IN ({placeholders})"
            cursor.execute(delete_query, chunk)
            total_deleted += cursor.rowcount
            
        print(f"\nSuccessfully removed {total_deleted} orphan record(s) from 'ticker_meta_profile'.")
        
        # 5. Clear cached calculations to ensure dashboard reflects changes
        clear_cache()
        
        return total_deleted


if __name__ == "__main__":
    delete_orphan_profiles()
