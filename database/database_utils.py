from datetime import datetime
from typing import List, Dict, Any
from database.schema_definitions import db_close

def get_close_price_records(ltickers: List[str], dates: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieves close price records matching the given tickers and dates from the db_close collection.
    
    The database uses a wide schema where each document represents a single day:
    {
        "Date": datetime.datetime(2023, 1, 25, 0, 0),
        "AAPL": 141.86,
        "MSFT": 240.61,
        ...
    }
    
    Args:
        ltickers: List of ticker symbols (strings)
        dates: List of dates (strings in YYYY-MM-DD format)
        
    Returns:
        List of matching MongoDB records (dictionaries), where each dict contains "Date"
        (as a string YYYY-MM-DD) and the requested tickers as keys.
    """
    if not ltickers or not dates:
        return []
        
    # Convert string dates to datetime objects (at midnight) as stored in MongoDB
    query_dates = []
    for d in dates:
        try:
            query_dates.append(datetime.strptime(d, "%Y-%m-%d"))
        except ValueError:
            pass
            
    if not query_dates:
        return []
        
    # Query matching documents from db_close
    query = {"Date": {"$in": query_dates}}
    
    # Project only Date and the requested tickers
    projection = {"_id": 0, "Date": 1}
    for ticker in ltickers:
        projection[ticker] = 1
        
    results = []
    for doc in db_close.find(query, projection):
        # Format the datetime back to a YYYY-MM-DD string
        date_val = doc.get("Date")
        record = {}
        if isinstance(date_val, datetime):
            record["Date"] = date_val.strftime("%Y-%m-%d")
        else:
            record["Date"] = str(date_val)
            
        # Copy the ticker values
        for ticker in ltickers:
            if ticker in doc:
                record[ticker] = doc[ticker]
                
        results.append(record)
        
    return results
