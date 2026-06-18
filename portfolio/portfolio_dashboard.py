import os
from flask import Flask, render_template, jsonify, request
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from utils.calendar_utils import get_nyse_business_days_comparison

app = Flask(__name__, template_folder='templates', static_folder='static')

def is_cash(symbol: str) -> bool:
    if not symbol:
        return False
    sym = symbol.upper()
    return sym.endswith('**') or sym in (
        'FDIC-INSURED DEPOSIT SWEEP',
        'PENDING ACTIVITY',
        'FCASH',
        'CASH',
        'PENDING',
        'MONEY MARKET'
    )

def get_latest_price(symbol: str) -> float:
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close_price 
            FROM market_data_close 
            WHERE ticker = ? 
            ORDER BY date DESC LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
    return None

def get_price_at_date(symbol: str, date_str: str) -> float:
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close_price 
            FROM market_data_close 
            WHERE ticker = ? AND date <= ? 
            ORDER BY date DESC LIMIT 1
        """, (symbol, date_str))
        row = cursor.fetchone()
        if row is not None:
            return float(row[0])
    return None

def fetch_portfolio_at_date(date_str: str, use_overall_latest_price: bool = False) -> dict:
    portfolio = {}
    cash_positions = []
    
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol, quantity, average_cost_basis, cost_basis_total, current_value, account_name, last_price, percent_of_account
            FROM fidelity_positions
            WHERE date = ?
        """, (date_str,))
        rows = cursor.fetchall()
        
    for row in rows:
        symbol, qty, avg_cost, total_cost, curr_val, acc_name, last_price, pct_acct = row
        
        if is_cash(symbol):
            cash_positions.append({
                'symbol': symbol,
                'current_value': curr_val or 0.0,
                'percent_of_account': pct_acct or 0.0,
                'account_name': acc_name or 'Cash'
            })
        else:
            # Resolve price
            if use_overall_latest_price:
                db_price = get_latest_price(symbol)
            else:
                db_price = get_price_at_date(symbol, date_str)
                
            if db_price is not None:
                curr_price = db_price
                price_source = 'db_close'
            else:
                curr_price = last_price if last_price is not None else 1.0
                price_source = 'fidelity_last_price'
                
            qty_val = qty if qty is not None else 0.0
            dynamic_value = qty_val * curr_price
            
            cost_basis_tot = total_cost if total_cost is not None else 0.0
            gain_loss_d = dynamic_value - cost_basis_tot
            gain_loss_p = (gain_loss_d / cost_basis_tot * 100) if cost_basis_tot > 0.0 else 0.0
            
            portfolio[symbol] = {
                'symbol': symbol,
                'account_name': acc_name,
                'quantity': qty,
                'average_cost_basis': avg_cost,
                'cost_basis_total': total_cost,
                'current_price': curr_price,
                'dynamic_value': dynamic_value,
                'gain_loss_dollar': gain_loss_d,
                'gain_loss_percent': gain_loss_p,
                'price_source': price_source,
                'percent_of_account': pct_acct
            }
            
    if cash_positions:
        total_cash_value = sum(p['current_value'] for p in cash_positions)
        mean_pct = sum(p['percent_of_account'] for p in cash_positions) / len(cash_positions)
        
        portfolio['Money Market'] = {
            'symbol': 'Money Market',
            'account_name': 'Cash',
            'quantity': None,
            'average_cost_basis': None,
            'cost_basis_total': None,
            'current_price': 1.0,
            'dynamic_value': total_cash_value,
            'gain_loss_dollar': 0.0,
            'gain_loss_percent': 0.0,
            'price_source': 'fidelity_last_price',
            'percent_of_account': mean_pct
        }
        
    return portfolio

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    init_sqlite_db()
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM fidelity_positions")
        row = cursor.fetchone()
        latest_date = row[0] if row else None
        
    if not latest_date:
        return jsonify({'date': None, 'positions': [], 'totals': {}})
        
    portfolio_dict = fetch_portfolio_at_date(latest_date, use_overall_latest_price=True)
    positions_list = list(portfolio_dict.values())
    
    total_value = sum(p['dynamic_value'] for p in positions_list if p['dynamic_value'] is not None)
    total_cost = sum(p['cost_basis_total'] for p in positions_list if p['cost_basis_total'] is not None and not is_cash(p['symbol']))
    
    total_gain_dollar = total_value - total_cost
    total_gain_percent = (total_gain_dollar / total_cost * 100) if total_cost > 0.0 else 0.0
    
    cash_value = sum(p['dynamic_value'] for p in positions_list if is_cash(p['symbol']))
    equity_value = sum(p['dynamic_value'] for p in positions_list if not is_cash(p['symbol']))
    
    totals = {
        'total_value': total_value,
        'total_cost': total_cost,
        'total_gain_dollar': total_gain_dollar,
        'total_gain_percent': total_gain_percent,
        'cash_value': cash_value,
        'equity_value': equity_value
    }
    
    return jsonify({
        'date': latest_date,
        'positions': positions_list,
        'totals': totals
    })

@app.route('/api/business-days')
def api_business_days():
    days = get_nyse_business_days_comparison()
    return jsonify(days)

@app.route('/api/snapshot-dates')
def api_snapshot_dates():
    init_sqlite_db()
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM fidelity_positions ORDER BY date DESC")
        dates = [row[0] for row in cursor.fetchall()]
    return jsonify(dates)

@app.route('/api/compare')
def api_compare():
    init_sqlite_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    business_days = get_nyse_business_days_comparison()
    
    if not start_date or not end_date:
        if len(business_days) >= 2:
            if not end_date:
                end_date = business_days[0]
            if not start_date:
                start_date = business_days[-1]
        else:
            with get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MIN(date), MAX(date) FROM fidelity_positions")
                min_d, max_d = cursor.fetchone()
                if not start_date:
                    start_date = min_d
                if not end_date:
                    end_date = max_d
                    
    if not start_date or not end_date:
        return jsonify({'error': 'No dates available'}), 400
        
    start_portfolio = fetch_portfolio_at_date(start_date)
    end_portfolio = fetch_portfolio_at_date(end_date)
    
    start_value = sum(p['dynamic_value'] for p in start_portfolio.values() if p['dynamic_value'] is not None)
    end_value = sum(p['dynamic_value'] for p in end_portfolio.values() if p['dynamic_value'] is not None)
    
    change_dollar = end_value - start_value
    change_percent = (change_dollar / start_value * 100) if start_value > 0.0 else 0.0
    
    totals = {
        'start_value': start_value,
        'end_value': end_value,
        'change_dollar': change_dollar,
        'change_percent': change_percent
    }
    
    compare_positions = []
    common_symbols = set(start_portfolio.keys()).intersection(set(end_portfolio.keys()))
    
    for symbol in common_symbols:
        start_pos = start_portfolio[symbol]
        end_pos = end_portfolio[symbol]
        
        s_val = start_pos['dynamic_value'] or 0.0
        e_val = end_pos['dynamic_value'] or 0.0
        
        if s_val == 0.0 or e_val == 0.0:
            continue
            
        if is_cash(symbol):
            c_dollar = 0.0
            c_percent = 0.0
        else:
            s_price = start_pos['current_price'] or 0.0
            e_price = end_pos['current_price'] or 0.0
            e_qty = end_pos['quantity'] or 0.0
            c_dollar = (e_price - s_price) * e_qty
            c_percent = ((e_price - s_price) / s_price * 100) if s_price > 0.0 else 0.0
            
        compare_positions.append({
            'symbol': symbol,
            'account_name': end_pos['account_name'] or start_pos['account_name'],
            'start_qty': start_pos['quantity'],
            'end_qty': end_pos['quantity'],
            'start_value': s_val,
            'end_value': e_val,
            'change_dollar': c_dollar,
            'change_percent': c_percent
        })
        
    return jsonify({
        'start_date': start_date,
        'end_date': end_date,
        'positions': compare_positions,
        'totals': totals
    })

if __name__ == '__main__':
    init_sqlite_db()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='127.0.0.1', port=port, debug=True)
