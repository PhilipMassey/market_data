import sys
import os
from datetime import datetime
import math

# Add project root to sys.path to enable imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_manager
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def clean_float(val):
    if val is None:
        return None
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return f_val
    except (ValueError, TypeError):
        return None

def migrate():
    print("Starting database migration for FidelityPositions from MongoDB to SQLite...")
    
    # 1. Initialize SQLite schema
    init_sqlite_db()
    
    # 2. Get MongoDB collection
    mongo_collection = db_manager.db['FidelityPositions']
    
    try:
        total_docs = mongo_collection.count_documents({})
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        print("Please ensure MongoDB is running and MONGO_URI is configured correctly.")
        return
        
    print(f"Found {total_docs} documents in MongoDB 'FidelityPositions'.")
    
    rows_to_insert = []
    count = 0
    
    for doc in mongo_collection.find():
        # Handle Date parsing
        date_val = doc.get("Date")
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str):
            try:
                # Try parsing standard formats
                if "T" in date_val:
                    date_str = date_val.split("T")[0]
                else:
                    date_str = datetime.strptime(date_val, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                date_str = date_val
        else:
            # Skip records without a valid date
            continue
            
        symbol = doc.get("Symbol")
        if not symbol or not isinstance(symbol, str):
            continue
            
        quantity = clean_float(doc.get("Quantity"))
        avg_cost = clean_float(doc.get("Average Cost Basis"))
        total_cost = clean_float(doc.get("Cost Basis Total"))
        curr_val = clean_float(doc.get("Current Value"))
        acc_name = doc.get("Account Name")
        if acc_name is not None:
            acc_name = str(acc_name)
            
        last_price = clean_float(doc.get("Last Price"))
        pct_acct = clean_float(doc.get("Percent Of Account"))
        
        rows_to_insert.append((
            date_str,
            symbol,
            quantity,
            avg_cost,
            total_cost,
            curr_val,
            acc_name,
            last_price,
            pct_acct
        ))
        
        count += 1
        if count % 1000 == 0:
            print(f"Processed {count}/{total_docs} documents...")
            
    if rows_to_insert:
        print(f"Prepared {len(rows_to_insert)} records. Inserting into SQLite...")
        try:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO fidelity_positions (
                        date,
                        symbol,
                        quantity,
                        average_cost_basis,
                        cost_basis_total,
                        current_value,
                        account_name,
                        last_price,
                        percent_of_account
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows_to_insert)
            print("Migration completed successfully!")
        except Exception as e:
            print(f"Error inserting into SQLite: {e}")
    else:
        print("No records found to migrate.")

if __name__ == "__main__":
    migrate()
