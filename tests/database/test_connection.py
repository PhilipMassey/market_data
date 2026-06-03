import pytest
from database.connection import DatabaseManager


def test_database_manager_is_singleton():
    """
    Test that the DatabaseManager correctly implements the Singleton pattern.
    Multiple instantiations should return the exact same object in memory.
    """
    manager1 = DatabaseManager()
    manager2 = DatabaseManager()

    assert manager1 is manager2


def test_database_manager_returns_correct_db(mock_db_manager):
    """
    Test that the db property returns the 'stock_market' database object.
    Uses the mocked db manager to avoid real connection attempts.
    """
    db = mock_db_manager.db

    assert db.name == 'stock_market'

