import pytest
from pymongo.collection import Collection

# Import the constants and handles to be tested
from database.schema_definitions import (
    DB_NAME,
    FIDELITY_POSITIONS_COLLECTION,
    MARKET_DATA_CLOSE_COLLECTION,
    MARKET_DATA_VOLUME_COLLECTION,
    SYMBOL_PROFILE_COLLECTION,
    SYMBOL_PROFILE_CACHE_COLLECTION,
    SYMBOL_INFO_COLLECTION,
    db_fidel_pos,
    db_close,
    db_volume,
    db_symbol_profile,
    db_symbol_profile_cache,
    db_symbol_info
)

def test_database_name_is_correct():
    """
    Verify the database name constant is correct.
    """
    assert DB_NAME == "stock_market"

def test_collection_name_constants_are_correct():
    """
    Verify that the string constants for collection names match the schema.
    """
    assert FIDELITY_POSITIONS_COLLECTION == "FidelityPositions"
    assert MARKET_DATA_CLOSE_COLLECTION == "market_data_close"
    assert MARKET_DATA_VOLUME_COLLECTION == "market_data_volume"
    assert SYMBOL_PROFILE_COLLECTION == "symbol_profile"
    assert SYMBOL_PROFILE_CACHE_COLLECTION == "symbol_profile_cache"
    assert SYMBOL_INFO_COLLECTION == "symbol_info"

def test_db_close_handle_name():
    """
    Explicitly verify that the db_close handle is for the 'market_data_close' collection.
    """
    assert db_close.name == 'market_data_close'

def test_collection_handles_are_valid(mock_db_manager):
    """
    Verify that the direct collection handles are valid Collection objects
    and that their names match the corresponding string constants.
    
    This test uses the 'mock_db_manager' fixture to ensure no real DB connection.
    """
    # A list of tuples, where each tuple is (handle, expected_name_constant)
    handles_to_test = [
        (db_fidel_pos, FIDELITY_POSITIONS_COLLECTION),
        (db_close, MARKET_DATA_CLOSE_COLLECTION),
        (db_volume, MARKET_DATA_VOLUME_COLLECTION),
        (db_symbol_profile, SYMBOL_PROFILE_COLLECTION),
        (db_symbol_profile_cache, SYMBOL_PROFILE_CACHE_COLLECTION),
        (db_symbol_info, SYMBOL_INFO_COLLECTION),
    ]

    for handle, expected_name in handles_to_test:
        # Check if the handle is a valid pymongo Collection instance
        assert isinstance(handle, Collection), f"Handle for '{expected_name}' is not a Collection object."
        
        # Check if the collection's name is correct
        assert handle.name == expected_name, f"Handle for '{expected_name}' has mismatched name '{handle.name}'."
