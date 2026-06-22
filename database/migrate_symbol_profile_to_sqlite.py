import sys
import os

# Add project root to sys.path to enable imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_manager
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from utils.ticker_reader import get_all_tickers

def migrate():
    print("Starting ticker metadata migration...")
    
    # 1. Initialize SQLite schema (ensures ticker_metadata exists)
    init_sqlite_db()
    
    # Check if local symbol_profile.json exists
    local_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'symbol_profile.json')
    
    rows_to_insert = []
    
    if os.path.exists(local_json_path):
        print(f"Found local JSON export at {local_json_path}. Migrating from JSON...")
        import json
        try:
            with open(local_json_path, 'r') as f:
                data = json.load(f)
            total_docs = len(data)
            print(f"Loaded {total_docs} records from local JSON.")
            
            for doc in data:
                symbol = doc.get("symbol")
                if not symbol:
                    continue
                ticker = str(symbol).strip().upper()
                if not ticker:
                    continue
                    
                sector = doc.get("sectorname")
                if sector is not None:
                    sector = str(sector).strip()
                    if sector == "Information Technology":
                        sector = "Technology"
                    
                industry = doc.get("primaryname")
                if industry is not None:
                    industry = str(industry).strip()
                    
                rows_to_insert.append((ticker, sector, industry))
        except Exception as e:
            print(f"Error reading local JSON file: {e}")
            sys.exit(1)
    else:
        print("Local JSON file not found. Connecting to MongoDB...")
        # 2. Get MongoDB collection
        mongo_collection = db_manager.db['symbol_profile']
        
        try:
            total_docs = mongo_collection.count_documents({})
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            print("Please ensure MongoDB is running and MONGO_URI is configured correctly.")
            sys.exit(1)
            
        print(f"Found {total_docs} documents in MongoDB 'symbol_profile'.")
        
        count = 0
        for doc in mongo_collection.find():
            symbol = doc.get("symbol")
            if not symbol:
                continue
            ticker = str(symbol).strip().upper()
            if not ticker:
                continue
                
            sector = doc.get("sectorname")
            if sector is not None:
                sector = str(sector).strip()
                if sector == "Information Technology":
                    sector = "Technology"
                
            industry = doc.get("primaryname")
            if industry is not None:
                industry = str(industry).strip()
                
            rows_to_insert.append((ticker, sector, industry))
            
            count += 1
            if count % 500 == 0:
                print(f"Processed {count}/{total_docs} documents...")
            
    if rows_to_insert:
        print(f"Inserting {len(rows_to_insert)} records into SQLite ticker_meta_profile...")
        try:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO ticker_meta_profile (ticker, sector, industry)
                    VALUES (?, ?, ?)
                """, rows_to_insert)
            print("Migration completed successfully!")
            
            # Post-migration cleanup: delete entries with no matching symbol/ticker in current ticker list
            tickers = get_all_tickers()
            if tickers:
                print(f"Cleaning up ticker_meta_profile: deleting entries not present in the current ticker list ({len(tickers)} tickers)...")
                placeholders = ', '.join(['?'] * len(tickers))
                with get_sqlite_conn() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        DELETE FROM ticker_meta_profile
                        WHERE ticker NOT IN ({placeholders})
                    """, tickers)
                    deleted_count = cursor.rowcount
                print(f"Cleaned up {deleted_count} entries from ticker_meta_profile.")
            else:
                print("Warning: Current ticker list is empty. Skipping cleanup to avoid purging all metadata.")
        except Exception as e:
            print(f"Error during SQLite operations: {e}")
            sys.exit(1)
    else:
        print("No records found to migrate.")


if __name__ == "__main__":
    migrate()
