import sys
import os
from datetime import datetime

# Add project root to sys.path to enable imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_manager
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def migrate():
    print("Starting database migration from MongoDB to SQLite...")
    
    # 1. Initialize SQLite schema
    init_sqlite_db()
    
    # 2. Get MongoDB collection
    mongo_collection = db_manager.db['market_data_close']
    
    try:
        total_docs = mongo_collection.count_documents({})
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        print("Please ensure MongoDB is running and MONGO_URI is configured correctly.")
        return
        
    print(f"Found {total_docs} documents in MongoDB 'market_data_close'.")
    
    rows_to_insert = []
    count = 0
    
    for doc in mongo_collection.find():
        date_val = doc.get("Date")
        if not isinstance(date_val, datetime):
            continue
        date_str = date_val.strftime("%Y-%m-%d")
        
        for key, value in doc.items():
            if key in ("_id", "Date"):
                continue
            # value is the price
            if value is not None:
                try:
                    val_float = float(value)
                    import math
                    if not math.isnan(val_float):
                        rows_to_insert.append((date_str, key, val_float))
                except (ValueError, TypeError):
                    pass
                    
        count += 1
        if count % 100 == 0:
            print(f"Processed {count}/{total_docs} documents...")
            
    if rows_to_insert:
        print(f"Inserting {len(rows_to_insert)} records into SQLite...")
        try:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO market_data_close (date, ticker, close_price)
                    VALUES (?, ?, ?)
                """, rows_to_insert)
            print("Migration completed successfully!")
        except Exception as e:
            print(f"Error inserting into SQLite: {e}")
    else:
        print("No records found to migrate.")

if __name__ == "__main__":
    migrate()
