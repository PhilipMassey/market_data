import pytest
import sqlite3
import datetime
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from database.migrate_fidelity_to_sqlite import migrate

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
        # Standard stock position
        {
            "Symbol": "AAPL",
            "Quantity": 31.0,
            "Average Cost Basis": 153.78,
            "Cost Basis Total": 4767.14,
            "Current Value": 5658.12,
            "Date": datetime.datetime(2024, 2, 23, 0, 0),
            "Account Name": "Stocks",
            "Last Price": 182.52,
            "Percent Of Account": 1.19
        },
        # Money market position (quantity/avg cost are nan, which should convert to None/NULL)
        {
            "Symbol": "SPAXX**",
            "Quantity": float('nan'),
            "Average Cost Basis": float('nan'),
            "Cost Basis Total": 0.0,
            "Current Value": 11436.94,
            "Date": datetime.datetime(2024, 3, 23, 0, 0),
            "Account Name": "Cash Account",
            "Last Price": 1.0,
            "Percent Of Account": 55.54
        },
        # Position with string ISO date format and missing optional fields
        {
            "Symbol": "MSFT",
            "Quantity": 10,
            "Average Cost Basis": 350.0,
            "Cost Basis Total": 3500.0,
            "Current Value": 4000.0,
            "Date": "2025-10-18T00:00:00Z"
        }
    ]
    mock_mongo_collection.count_documents.return_value = len(mock_docs)
    mock_mongo_collection.find.return_value = mock_docs
    
    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()
        
    with patch('database.migrate_fidelity_to_sqlite.get_sqlite_conn', _get_conn), \
         patch('database.migrate_fidelity_to_sqlite.init_sqlite_db'), \
         patch('database.migrate_fidelity_to_sqlite.db_manager') as mock_db_mgr:
         
        # Make db_manager return the mock collection
        mock_db_mgr.db = {"FidelityPositions": mock_mongo_collection}
        
        # Manually create the table for the in-memory SQLite database
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fidelity_positions (
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL,
                average_cost_basis REAL,
                cost_basis_total REAL,
                current_value REAL,
                account_name TEXT,
                last_price REAL,
                percent_of_account REAL,
                PRIMARY KEY (date, symbol)
            )
        """)
        conn.commit()
        
        yield conn, mock_mongo_collection
    
    conn.close()

def test_migrate_fidelity_positions_success(mock_db_env):
    """
    Verify that migrate() parses and inserts the MongoDB records into SQLite properly.
    """
    conn, mock_mongo = mock_db_env
    
    # Run the migration
    migrate()
    
    # Verify records in SQLite
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, symbol, quantity, average_cost_basis, cost_basis_total, current_value, account_name, last_price, percent_of_account 
        FROM fidelity_positions
        ORDER BY date ASC, symbol ASC
    """)
    rows = cursor.fetchall()
    
    assert len(rows) == 3
    
    # 1. AAPL
    assert rows[0] == ("2024-02-23", "AAPL", 31.0, 153.78, 4767.14, 5658.12, "Stocks", 182.52, 1.19)
    
    # 2. SPAXX** (NaN quantity & average_cost_basis should become None in SQLite)
    assert rows[1] == ("2024-03-23", "SPAXX**", None, None, 0.0, 11436.94, "Cash Account", 1.0, 55.54)
    
    # 3. MSFT (String date, missing optional fields should be None)
    assert rows[2] == ("2025-10-18", "MSFT", 10.0, 350.0, 3500.0, 4000.0, None, None, None)
