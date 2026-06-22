import pytest
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from database.migrate_symbol_profile_to_sqlite import migrate

@pytest.fixture
def mock_db_env():
    """
    Fixture that creates an in-memory SQLite database and patches the MongoDB connection
    and schema creation to run the migration script in isolation.
    """
    # 1. Setup in-memory SQLite connection
    conn = sqlite3.connect(':memory:')
    
    # 2. Setup mock MongoDB data
    mock_mongo_collection = MagicMock()
    mock_docs = [
        {
            "symbol": "AAPL",
            "sectorname": "Information Technology",
            "primaryname": "Technology Hardware, Storage and Peripherals"
        },
        {
            "symbol": "msft ",
            "sectorname": "Information Technology ",
            "primaryname": "Systems Software"
        },
        {
            "symbol": "GOOG",
            "sectorname": None,
            "primaryname": "Interactive Media and Services"
        },
        {
            # Missing symbol - should be ignored
            "sectorname": "Financials",
            "primaryname": "Asset Management"
        }
    ]
    mock_mongo_collection.count_documents.return_value = len(mock_docs)
    mock_mongo_collection.find.return_value = mock_docs
    
    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()
        
    with patch('database.migrate_symbol_profile_to_sqlite.get_sqlite_conn', _get_conn), \
         patch('database.migrate_symbol_profile_to_sqlite.init_sqlite_db'), \
         patch('database.migrate_symbol_profile_to_sqlite.get_all_tickers', return_value=["AAPL", "MSFT", "GOOG"]), \
         patch('database.migrate_symbol_profile_to_sqlite.db_manager') as mock_db_mgr:
         
        # Make db_manager return the mock collection
        mock_db_mgr.db = {"symbol_profile": mock_mongo_collection}
        
        # Manually create the table for the in-memory SQLite database
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_meta_profile (
                ticker TEXT PRIMARY KEY NOT NULL,
                sector TEXT,
                industry TEXT
            )
        """)
        conn.commit()
        
        yield conn, mock_mongo_collection
    
    conn.close()

def test_migrate_symbol_profile_success(mock_db_env):
    """
    Verify that migrate() parses and inserts the MongoDB records into SQLite properly.
    """
    conn, mock_mongo = mock_db_env
    
    # Run the migration
    migrate()
    
    # Verify records in SQLite
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, sector, industry 
        FROM ticker_meta_profile
        ORDER BY ticker ASC
    """)
    rows = cursor.fetchall()
    
    # We expect 3 rows (AAPL, MSFT, GOOG). The 4th document has no symbol and should be skipped.
    assert len(rows) == 3
    
    # 1. AAPL (clean)
    assert rows[0] == ("AAPL", "Technology", "Technology Hardware, Storage and Peripherals")
    
    # 2. GOOG (null sector)
    assert rows[1] == ("GOOG", None, "Interactive Media and Services")
    
    # 3. MSFT (whitespace trimmed, uppercase ticker symbol)
    assert rows[2] == ("MSFT", "Technology", "Systems Software")


def test_migrate_symbol_profile_deletes_unmatched_tickers(mock_db_env):
    """
    Verify that migrate() deletes records that are not in the current ticker list.
    """
    conn, mock_mongo = mock_db_env
    
    with patch('database.migrate_symbol_profile_to_sqlite.get_all_tickers', return_value=["AAPL", "MSFT"]):
        migrate()
        
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, sector, industry 
        FROM ticker_meta_profile
        ORDER BY ticker ASC
    """)
    rows = cursor.fetchall()
    
    assert len(rows) == 2
    assert rows[0] == ("AAPL", "Technology", "Technology Hardware, Storage and Peripherals")
    assert rows[1] == ("MSFT", "Technology", "Systems Software")


def test_migrate_symbol_profile_from_json():
    """
    Verify that migrate() parses and inserts the local JSON records into SQLite properly.
    """
    import json
    from database.migrate_symbol_profile_to_sqlite import migrate
    
    # Create test data
    test_data = [
        {
            "symbol": "MSFT",
            "sectorname": "Tech",
            "primaryname": "Software"
        },
        {
            "symbol": "  tsla  ",
            "sectorname": "Automotive",
            "primaryname": "EV"
        }
    ]
    
    mock_exists = lambda path: path.endswith("symbol_profile.json")
    mock_open_content = json.dumps(test_data)
    
    from unittest.mock import patch, mock_open
    
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_meta_profile (
            ticker TEXT PRIMARY KEY NOT NULL,
            sector TEXT,
            industry TEXT
        )
    """)
    conn.commit()
    
    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()
        
    with patch('database.migrate_symbol_profile_to_sqlite.get_sqlite_conn', _get_conn), \
         patch('database.migrate_symbol_profile_to_sqlite.init_sqlite_db'), \
         patch('database.migrate_symbol_profile_to_sqlite.get_all_tickers', return_value=["MSFT", "TSLA"]), \
         patch('os.path.exists', mock_exists), \
         patch('builtins.open', mock_open(read_data=mock_open_content)):
         
        migrate()
        
    # Verify records in SQLite
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, sector, industry FROM ticker_meta_profile ORDER BY ticker")
    rows = cursor.fetchall()
    
    assert len(rows) == 2
    assert rows[0] == ("MSFT", "Tech", "Software")
    assert rows[1] == ("TSLA", "Automotive", "EV")
    conn.close()

