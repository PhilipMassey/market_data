import sqlite3
from collections import defaultdict

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def list_sectors_and_industries():
    """
    Connects to the database and displays all unique sectors, industries,
    and the count of tickers classified under each.
    """
    init_sqlite_db()
    
    query = """
        SELECT sector, industry, COUNT(ticker) as ticker_count
        FROM ticker_meta_profile
        GROUP BY sector, industry
        ORDER BY sector ASC, ticker_count DESC
    """
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
    # Group results in memory
    sector_tree = defaultdict(list)
    total_tickers = 0
    unique_sectors = set()
    unique_industries = set()
    
    for sector, industry, count in rows:
        sector_name = sector or "Unknown"
        industry_name = industry or "Unknown"
        sector_tree[sector_name].append((industry_name, count))
        
        unique_sectors.add(sector_name)
        unique_industries.add(industry_name)
        total_tickers += count
        
    print("=" * 60)
    print("      DATABASE SECTOR & INDUSTRY METADATA SUMMARY      ")
    print("=" * 60)
    print(f"Total Tickers in Profile: {total_tickers}")
    print(f"Unique Sectors:           {len(unique_sectors)}")
    print(f"Unique Industries:        {len(unique_industries)}")
    print("=" * 60)
    print()
    
    for sector, industries in sorted(sector_tree.items()):
        sector_total = sum(count for _, count in industries)
        print(f"📁 Sector: {sector} ({sector_total} tickers)")
        print("-" * 50)
        for industry, count in industries:
            print(f"  └── {industry:<35} : {count} tickers")
        print()
    print("=" * 60)

if __name__ == "__main__":
    list_sectors_and_industries()
