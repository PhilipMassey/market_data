import pytest
from mongomock import MongoClient
from unittest.mock import patch

@pytest.fixture(scope="function")
def mock_db_manager():
    """
    Pytest fixture to patch the db_manager with a mongomock client.
    This ensures that tests do not interact with the real database.
    The patch is applied to 'database.connection.db_manager' where it is defined.
    """
    with patch('database.connection.db_manager') as mock_manager:
        # Configure the mock to use a mongomock client
        mock_client = MongoClient()
        mock_manager.client = mock_client
        mock_manager.db = mock_client['stock_market']
        
        yield mock_manager
        
        # Teardown: clear the mock database after each test
        mock_client.drop_database('stock_market')
