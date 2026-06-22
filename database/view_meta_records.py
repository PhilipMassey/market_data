import os
import sqlite3
import pandas as pd

def view_meta_records(limit=100, sector=None):
    """
    Connects to the SQLite database and loads the ticker_meta_profile records into a Pandas DataFrame.
    
    Args:
        limit (int): Maximum number of records to return. Pass None for all records.
        sector (str): Filter records by a specific sector name.
        
    Returns:
        pd.DataFrame: DataFrame containing ticker, sector, and industry columns.
    """
    # Resolve directory path: try PYTHONPATH first
    pythonpath = os.environ.get('PYTHONPATH')
    db_path = None
    if pythonpath:
        # PYTHONPATH can contain multiple paths separated by ':' on macOS/Linux
        for p in pythonpath.split(':'):
            possible_path = os.path.join(p.strip(), 'database', 'market_data.db')
            if os.path.exists(possible_path):
                db_path = possible_path
                break
                
    # Fallback path resolution
    if not db_path or not os.path.exists(db_path):
        base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
        db_path = os.path.join(base_dir, 'market_data.db')
        
    if not db_path or not os.path.exists(db_path):
        print("Error: Database file market_data.db not found.")
        return None
        
    conn = sqlite3.connect(db_path)
    
    query = "SELECT * FROM ticker_meta_profile"
    params = []
    
    if sector:
        query += " WHERE sector = ?"
        params.append(sector)
        
    query += " ORDER BY ticker ASC"
    
    if limit:
        query += " LIMIT ?"
        params.append(limit)
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    print(f"Loaded {len(df)} records from {db_path}.")
    return df

if __name__ == "__main__":
    # Standard terminal check: view first 10 records
    df = view_meta_records(limit=10)
    if df is not None:
        print("\nFirst 10 records:")
        print(df.to_string(index=False))
