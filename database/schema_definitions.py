from database.connection import db_manager

# --- Database Name ---
DB_NAME = "stock_market"

# --- Collection Names (as strings) ---
FIDELITY_POSITIONS_COLLECTION = "FidelityPositions"
MARKET_DATA_CLOSE_COLLECTION = "market_data_close"
MARKET_DATA_VOLUME_COLLECTION = "market_data_volume"
SYMBOL_PROFILE_COLLECTION = "symbol_profile"
SYMBOL_PROFILE_CACHE_COLLECTION = "symbol_profile_cache"
SYMBOL_INFO_COLLECTION = "symbol_info"
TEST_CLOSE_COLLECTION = "test_close"
TEST_VOLUME_COLLECTION = "test_volume"

# --- Direct Collection Handles (for convenient access) ---
# These variables provide direct access to the collection objects.
# Example usage: db_close.find_one({"ticker": "AAPL"})

db_fidelity_positions = db_manager.db[FIDELITY_POSITIONS_COLLECTION]
db_close = db_manager.db[MARKET_DATA_CLOSE_COLLECTION]
db_volume = db_manager.db[MARKET_DATA_VOLUME_COLLECTION]
db_symbol_profile = db_manager.db[SYMBOL_PROFILE_COLLECTION]
db_symbol_profile_cache = db_manager.db[SYMBOL_PROFILE_CACHE_COLLECTION]
db_symbol_info = db_manager.db[SYMBOL_INFO_COLLECTION]
db_test_close = db_manager.db[TEST_CLOSE_COLLECTION]
db_test_vol = db_manager.db[TEST_VOLUME_COLLECTION]

# You can now import these variables from any other module, for example:
# from database.schema_definitions import db_close, SYMBOL_PROFILE_COLLECTION
