import os
from pymongo import MongoClient
from pymongo.database import Database

class DatabaseManager:
    """
    Singleton Connection manager for MongoDB.
    """
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            # Initialize connection on first instantiation
            mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
            cls._client = MongoClient(mongo_uri)
        return cls._instance

    @property
    def client(self) -> MongoClient:
        return self._client

    @property
    def db(self) -> Database:
        """Returns the primary stock_market database."""
        return self._client['stock_market']

# Create a global instance to be imported by other modules
db_manager = DatabaseManager()
