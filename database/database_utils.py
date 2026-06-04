from typing import List, Dict, Any
from database.schema_definitions import db_close

def get_close_price_records(ltickers: List[str], dates: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieves close price records matching the given tickers and dates from the db_close collection.
    
    Args:
        ltickers: List of ticker symbols (strings)
        dates: List of dates (strings in YYYY-MM-DD format)
        
    Returns:
        List of matching MongoDB records (dictionaries), excluding the '_id' field.
    """
    if not ltickers or not dates:
        return []
        
    query = {
        "ticker": {"$in": ltickers},
        "date": {"$in": dates}
    }
    
    # Exclude the MongoDB ObjectId '_id' for clean dictionaries
    projection = {"_id": 0}
    
    return list(db_close.find(query, projection))
