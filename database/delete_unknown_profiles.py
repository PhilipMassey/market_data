import os
import sys

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn, init_sqlite_db

def delete_unknown_profiles():
    """
    Deletes all records from ticker_meta_profile that have 'Unknown' values,
    allowing the updater to retry fetching metadata for them.
    """
    init_sqlite_db()
    
    query_select = """
        SELECT ticker, company_name, type, sector, industry
        FROM ticker_meta_profile
        WHERE company_name = 'Unknown'
           OR type = 'Unknown'
           OR sector = 'Unknown'
           OR industry = 'Unknown'
    """
    
    query_delete = """
        DELETE FROM ticker_meta_profile
        WHERE company_name = 'Unknown'
           OR type = 'Unknown'
           OR sector = 'Unknown'
           OR industry = 'Unknown'
    """
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch them first to display
        cursor.execute(query_select)
        rows = cursor.fetchall()
        
        if not rows:
            print("No profiles with 'Unknown' values found in database.")
            return
            
        print(f"Found {len(rows)} profiles with 'Unknown' values to delete:")
        for r in rows[:20]:
            print(f"  - {r[0]}: Name='{r[1]}' | Type={r[2]} | Sector={r[3]} | Industry={r[4]}")
            
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more.")
            
        # 2. Perform deletion
        cursor.execute(query_delete)
        deleted_count = cursor.rowcount
        print(f"\nSuccessfully deleted {deleted_count} 'Unknown' metadata records from ticker_meta_profile.")

if __name__ == "__main__":
    delete_unknown_profiles()
