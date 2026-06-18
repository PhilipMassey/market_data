import pytest
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch
from portfolio.portfolio_dashboard import app, is_cash

def test_is_cash():
    assert is_cash("SPAXX**") is True
    assert is_cash("FDRXX**") is True
    assert is_cash("CORE**") is True
    assert is_cash("FDIC-INSURED DEPOSIT SWEEP") is True
    assert is_cash("AAPL") is False
    assert is_cash("MSFT") is False
    assert is_cash("EWY") is False

@pytest.fixture
def mock_sqlite_db():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # Create tables
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_close (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    """)
    
    # Insert dummy fidelity positions (snapshot date: 2026-06-07 and 2026-06-01)
    cursor.executemany("""
        INSERT INTO fidelity_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        # Snapshot 2026-06-01
        ('2026-06-01', 'AAPL', 10.0, 140.0, 1400.0, 1400.0, 'Stocks', 140.0, 50.0),
        ('2026-06-01', 'SPAXX**', None, None, None, 1000.0, 'Cash', 1.0, 50.0),
        
        # Snapshot 2026-06-07
        # AAPL: quantity=10, cost_basis=1400, last_price=145
        ('2026-06-07', 'AAPL', 10.0, 140.0, 1400.0, 1450.0, 'Stocks', 145.0, 40.0),
        # SPAXX**: cash sweep, current_value=1000
        ('2026-06-07', 'SPAXX**', None, None, None, 1000.0, 'Cash', 1.0, 20.0),
        # FDRXX**: cash sweep, current_value=500
        ('2026-06-07', 'FDRXX**', None, None, None, 500.0, 'Cash', 1.0, 20.0),
        # CORE**: cash sweep, current_value=500
        ('2026-06-07', 'CORE**', None, None, None, 500.0, 'Cash', 1.0, 20.0),
        # Pending activity: cash sweep, current_value=-200
        ('2026-06-07', 'Pending activity', None, None, None, -200.0, 'Cash', 1.0, 10.0)
    ])
    
    # Insert close prices
    cursor.executemany("""
        INSERT INTO market_data_close VALUES (?, ?, ?)
    """, [
        # Latest price for AAPL is 150 on 2026-06-08 (more recent than snapshot)
        ('2026-06-08', 'AAPL', 150.0),
        # Price on 2026-06-06 (used for 2026-06-07 end_date)
        ('2026-06-06', 'AAPL', 144.0),
        # Price on 2026-06-01 (used for 2026-06-01 start_date)
        ('2026-06-01', 'AAPL', 140.0)
    ])
    
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    with patch('portfolio.portfolio_dashboard.get_sqlite_conn', _get_conn), \
         patch('portfolio.portfolio_dashboard.init_sqlite_db'):
        yield conn
    conn.close()

def test_home_route():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b"Portfolio Valuation Dashboard" in response.data

def test_api_portfolio_route(mock_sqlite_db):
    client = app.test_client()
    response = client.get('/api/portfolio')
    assert response.status_code == 200
    
    data = response.json
    assert data is not None
    assert data['date'] == '2026-06-07'
    assert 'positions' in data
    assert 'totals' in data
    
    positions = data['positions']
    assert len(positions) == 2
    
    # Verify AAPL position details (joined with market_data_close)
    aavel = next(p for p in positions if p['symbol'] == 'AAPL')
    assert aavel['quantity'] == 10.0
    assert aavel['current_price'] == 150.0 # From market_data_close (latest date 2026-06-08)
    assert aavel['dynamic_value'] == 1500.0 # 10 * 150.0
    assert aavel['cost_basis_total'] == 1400.0
    assert aavel['gain_loss_dollar'] == 100.0 # 1500 - 1400
    assert aavel['gain_loss_percent'] == pytest.approx(7.1428, abs=1e-3)
    assert aavel['price_source'] == 'db_close'
    
    # Verify rolled-up Money Market position details
    mm = next(p for p in positions if p['symbol'] == 'Money Market')
    assert mm['quantity'] is None
    assert mm['current_price'] == 1.0 # fallback default/last price
    assert mm['dynamic_value'] == 1800.0 # 1000 + 500 + 500 - 200 (sum of cash sweeps)
    assert mm['price_source'] == 'fidelity_last_price'
    assert mm['percent_of_account'] == pytest.approx(17.5) # Mean of 20.0, 20.0, 20.0, 10.0
    
    # Verify totals
    # total_value = AAPL (1500) + Money Market (1800) = 3300
    # total_cost = AAPL (1400) = 1400
    # gain_dollar = 3300 - 1400 = 1900
    # gain_percent = (1900 / 1400) * 100 = 135.714%
    # cash = 1800, equity = 1500
    totals = data['totals']
    assert totals['total_value'] == 3300.0
    assert totals['total_cost'] == 1400.0
    assert totals['total_gain_dollar'] == 1900.0
    assert totals['total_gain_percent'] == pytest.approx(135.7142, abs=1e-3)
    assert totals['cash_value'] == 1800.0
    assert totals['equity_value'] == 1500.0

def test_api_business_days_route():
    # Test that the business-days endpoint returns a list of days
    with patch('portfolio.portfolio_dashboard.get_nyse_business_days_comparison') as mock_get_days:
        mock_get_days.return_value = ['2026-06-08', '2026-06-05', '2026-06-04']
        
        client = app.test_client()
        response = client.get('/api/business-days')
        assert response.status_code == 200
        data = response.json
        assert data == ['2026-06-08', '2026-06-05', '2026-06-04']

def test_api_compare_route(mock_sqlite_db):
    # Test that compare endpoint calculates valuation differences correctly
    with patch('portfolio.portfolio_dashboard.get_nyse_business_days_comparison') as mock_get_days:
        mock_get_days.return_value = ['2026-06-07', '2026-06-01']
        
        client = app.test_client()
        
        # Test with explicit parameters
        response = client.get('/api/compare?start_date=2026-06-01&end_date=2026-06-07')
        assert response.status_code == 200
        
        data = response.json
        assert data['start_date'] == '2026-06-01'
        assert data['end_date'] == '2026-06-07'
        
        # Verify totals
        totals = data['totals']
        # Start:
        # AAPL: 10 * 140.0 = 1400.0
        # MM (SPAXX): 1000.0
        # Total Start: 2400.0
        #
        # End:
        # AAPL: 10 * 144.0 = 1440.0
        # MM (SPAXX + FDRXX + CORE + Pending): 1000 + 500 + 500 - 200 = 1800.0
        # Total End: 3240.0
        #
        # Delta:
        # change_dollar: 3240.0 - 2400.0 = 840.0
        # change_percent: (840.0 / 2400.0) * 100 = 35.0%
        assert totals['start_value'] == 2400.0
        assert totals['end_value'] == 3240.0
        assert totals['change_dollar'] == 840.0
        assert totals['change_percent'] == pytest.approx(35.0)
        
        # Verify individual positions
        positions = data['positions']
        assert len(positions) == 2
        
        aapl = next(p for p in positions if p['symbol'] == 'AAPL')
        assert aapl['account_name'] == 'Stocks'
        assert aapl['start_value'] == 1400.0
        assert aapl['end_value'] == 1440.0
        assert aapl['change_dollar'] == 40.0
        assert aapl['change_percent'] == pytest.approx(2.8571, abs=1e-3)
        
        mm = next(p for p in positions if p['symbol'] == 'Money Market')
        assert mm['account_name'] == 'Cash'
        assert mm['start_value'] == 1000.0
        assert mm['end_value'] == 1800.0
        assert mm['change_dollar'] == 0.0
        assert mm['change_percent'] == 0.0

def test_api_compare_route_defaults(mock_sqlite_db):
    # Test that compare endpoint falls back to defaults if no dates provided
    with patch('portfolio.portfolio_dashboard.get_nyse_business_days_comparison') as mock_get_days:
        mock_get_days.return_value = ['2026-06-07', '2026-06-01']
        
        client = app.test_client()
        response = client.get('/api/compare')
        assert response.status_code == 200
        
        data = response.json
        assert data['start_date'] == '2026-06-01'
        assert data['end_date'] == '2026-06-07'

def test_api_compare_quantity_change():
    # Test that compare endpoint calculates gains/losses correctly when quantity changes
    with patch('portfolio.portfolio_dashboard.get_nyse_business_days_comparison') as mock_get_days, \
         patch('portfolio.portfolio_dashboard.fetch_portfolio_at_date') as mock_fetch_at_date, \
         patch('portfolio.portfolio_dashboard.get_price_at_date') as mock_get_price:
         
        mock_get_days.return_value = ['2026-06-07', '2026-06-01']
        
        # Define mock portfolios
        # Start: AAPL (10 shares @ 140.0 = 1400.0), GOOG (5 shares @ 160.0 = 800.0)
        start_portfolio = {
            'AAPL': {
                'symbol': 'AAPL',
                'account_name': 'Stocks',
                'quantity': 10.0,
                'current_price': 140.0,
                'dynamic_value': 1400.0
            },
            'GOOG': {
                'symbol': 'GOOG',
                'account_name': 'Stocks',
                'quantity': 5.0,
                'current_price': 160.0,
                'dynamic_value': 800.0
            }
        }
        # End: AAPL (12 shares @ 150.0 = 1800.0), MSFT (4 shares @ 250.0 = 1000.0)
        # GOOG sold (quantity=0, dynamic_value=0.0)
        end_portfolio = {
            'AAPL': {
                'symbol': 'AAPL',
                'account_name': 'Stocks',
                'quantity': 12.0,
                'current_price': 150.0,
                'dynamic_value': 1800.0
            },
            'MSFT': {
                'symbol': 'MSFT',
                'account_name': 'Stocks',
                'quantity': 4.0,
                'current_price': 250.0,
                'dynamic_value': 1000.0
            }
        }
        
        def side_effect(date):
            if date == '2026-06-01':
                return start_portfolio
            return end_portfolio
            
        mock_fetch_at_date.side_effect = side_effect
        mock_get_price.return_value = 160.0
        
        client = app.test_client()
        response = client.get('/api/compare?start_date=2026-06-01&end_date=2026-06-07')
        assert response.status_code == 200
        
        data = response.json
        
        # Verify totals (Net Asset Change must include GOOG and MSFT)
        # Start total = AAPL (1400.0) + GOOG (800.0) = 2200.0
        # End total = AAPL (1800.0) + MSFT (1000.0) = 2800.0
        # Change total = 600.0
        # Change percent = (600.0 / 2200.0) * 100 = 27.2727%
        totals = data['totals']
        assert totals['start_value'] == 2200.0
        assert totals['end_value'] == 2800.0
        assert totals['change_dollar'] == 600.0
        assert totals['change_percent'] == pytest.approx(27.2727, abs=1e-3)
        
        # Verify that GOOG (sale) and MSFT (buy) are dropped from detailed positions list
        positions = data['positions']
        # Only AAPL should remain, as GOOG has end_value=0.0 and MSFT has start_value=0.0
        assert len(positions) == 1
        
        aapl = positions[0]
        assert aapl['symbol'] == 'AAPL'
        assert aapl['start_qty'] == 10.0
        assert aapl['end_qty'] == 12.0
        assert aapl['change_dollar'] == 120.0 # (150.0 - 140.0) * 12.0
        assert aapl['change_percent'] == pytest.approx(7.1428, abs=1e-3)
