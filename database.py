import os
from typing import List, Dict, Any
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

def get_db_connection() -> MongoClient:
    """
    Establishes a connection to the MongoDB server.
    Requires MONGO_URI environment variable to be set.
    """
    mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    client: MongoClient = MongoClient(mongo_uri)
    return client

def get_database(client: MongoClient) -> Database:
    """
    Returns the stock_market database.
    """
    return client['stock_market']

def get_close_price_collection(db: Database) -> Collection:
    """
    Returns the market_data_close collection.
    """
    return db['market_data_close']

def insert_close_prices(collection: Collection, data: List[Dict[str, Any]]) -> None:
    """
    Inserts a list of closing price documents into the collection.
    Ignores duplicates if a unique index on (ticker, date) exists.
    """
    if not data:
        return
    # Optional: could use insert_many with ordered=False to ignore duplicate key errors
    collection.insert_many(data)
