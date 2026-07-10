import os
import sys
import math
import datetime
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

# Add project root to sys.path if not already present
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.sqlite_connection import get_sqlite_conn
from database.database_utils import get_close_price_records
from utils.calendar_utils import get_nyse_business_days_comparison
from utils.ticker_reader import get_all_tickers

# Global cache for rankings
global_cache = {
    'date': None,
    'df_all_periods': None
}

def get_ndays_for_period(period_name: str, business_days: List[str]) -> List[int]:
    """
    Given a period name, calculates the list of ndays offsets from the newest trading day.
    """
    if not business_days:
        return []
        
    latest_date_str = business_days[0]
    latest_dt = datetime.datetime.strptime(latest_date_str, '%Y-%m-%d')
    
    if period_name == 'Daily':
        # [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0] days ago
        return list(range(10, -1, -1))
        
    elif period_name == '1 Week':
        intervals = [relativedelta(weeks=w) for w in range(6, 0, -1)]
    elif period_name == '2 Weeks':
        intervals = [relativedelta(weeks=w) for w in range(12, 0, -2)]
    elif period_name == '1 Month':
        intervals = [relativedelta(months=m) for m in range(6, 0, -1)]
    elif period_name == '2 Months':
        intervals = [relativedelta(months=m) for m in range(12, 0, -2)]
    else:
        raise ValueError(f"Unknown period: {period_name}")
        
    offsets = []
    # Helper to find index of closest date <= target
    for rd in intervals:
        target_dt = latest_dt - rd
        target_str = target_dt.strftime('%Y-%m-%d')
        # Find index in business_days (newest to oldest)
        found_idx = len(business_days) - 1
        for idx, b_day in enumerate(business_days):
            if b_day <= target_str:
                found_idx = idx
                break
        offsets.append(found_idx)
        
    # Append index 0 (latest completed trading day)
    offsets.append(0)
    
    # Return unique sorted descending (oldest to newest in index value, i.e. highest to lowest)
    return sorted(list(set(offsets)), reverse=True)

def get_df_closings_for_ndays_range(ndays_range: List[int], symbols: List[str], business_days: List[str]) -> pd.DataFrame:
    """
    Retrieves closing prices for a list of symbols and ndays offsets from the SQLite database.
    """
    if not ndays_range or not symbols or not business_days:
        return pd.DataFrame(columns=symbols)
        
    # Map ndays offsets to actual dates
    dates = []
    for n in ndays_range:
        if n < len(business_days):
            dates.append(business_days[n])
            
    # Retrieve wide-format records
    records = get_close_price_records(symbols, dates)
    if not records:
        return pd.DataFrame(columns=symbols)
        
    df_all = pd.DataFrame(records)
    df_all.set_index('Date', inplace=True)
    
    # Ensure all symbols exist as columns
    for sym in symbols:
        if sym not in df_all.columns:
            df_all[sym] = np.nan
            
    return df_all

def df_overall_performance(ndays_range: List[int], symbols: List[str], business_days: List[str]) -> pd.DataFrame:
    """
    Calculates overall performance metrics for symbols over a given date range.
    """
    df_all = get_df_closings_for_ndays_range(ndays_range, symbols, business_days)
    
    if df_all.empty:
        return pd.DataFrame(columns=['symbol', 'over_pc', 'pc_mean', 'pc_std', 'risk_reward'])
        
    # Calculate overall percentage based on first valid and last valid price
    first_valid = df_all.bfill().iloc[0] if len(df_all) > 0 else pd.Series(dtype=float)
    last_valid = df_all.ffill().iloc[-1] if len(df_all) > 0 else pd.Series(dtype=float)
    
    # Avoid division by zero
    df_over_pct = pd.Series(index=symbols, dtype=float)
    for sym in symbols:
        fv = first_valid.get(sym)
        lv = last_valid.get(sym)
        if pd.notna(fv) and pd.notna(lv) and fv != 0:
            df_over_pct[sym] = ((lv - fv) / fv) * 100
        else:
            df_over_pct[sym] = np.nan
            
    df_vars = pd.DataFrame(df_over_pct, columns=['over_pc'])
    
    # Calculate period pct change
    df_period_pct = df_all.pct_change(periods=1) * 100
    
    # Calculate metrics ignoring NaNs
    df_vars['pc_mean'] = df_period_pct.mean()
    df_vars['pc_std'] = df_period_pct.std()
    
    # Risk-Reward Proxy (Sharpe-like ratio)
    df_vars['risk_reward'] = np.where(
        df_vars['pc_std'].notna() & (df_vars['pc_std'] != 0),
        df_vars['pc_mean'] / df_vars['pc_std'],
        0.0
    )
    
    df_vars.reset_index(inplace=True)
    df_vars.rename(columns={'index': 'symbol'}, inplace=True)
    df_vars = df_vars.round(3)
    return df_vars

def df_perc_by_sector_industry(symbols: List[str]) -> pd.DataFrame:
    """
    Retrieves sector and industry mapping from the ticker_meta_profile SQLite table.
    """
    if not symbols:
        return pd.DataFrame(columns=['symbol', 'sector', 'industry'])
        
    placeholders = ', '.join(['?'] * len(symbols))
    query = f"""
        SELECT ticker, sector, industry
        FROM ticker_meta_profile
        WHERE ticker IN ({placeholders})
    """
    
    records = []
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, symbols)
        for row in cursor.fetchall():
            records.append({
                'symbol': row[0],
                'sector': row[1] or 'Unknown',
                'industry': row[2] or 'Unknown'
            })
            
    df = pd.DataFrame(records)
    if df.empty:
        # Create empty DataFrame with correct columns if no records found
        return pd.DataFrame(columns=['symbol', 'sector', 'industry'])
        
    return df

def df_secind_sym_perf(ndays_range: List[int], symbols: List[str], business_days: List[str]) -> pd.DataFrame:
    """
    Combines sector/industry profile with the calculated performance metrics.
    """
    df_over_perf = df_overall_performance(ndays_range, symbols, business_days)
    df_sector_ind = df_perc_by_sector_industry(symbols)
    
    # Merge using a left join anchored on performance
    df_merged = df_over_perf.merge(df_sector_ind, on='symbol', how='left')
    
    # Fill in defaults if sector/industry is missing
    df_merged['sector'] = df_merged['sector'].fillna('Unknown')
    df_merged['industry'] = df_merged['industry'].fillna('Unknown')
    
    cols = ['sector', 'industry', 'symbol', 'over_pc', 'pc_mean', 'pc_std', 'risk_reward']
    return df_merged[cols].sort_values(by=['sector', 'industry', 'symbol'])

def get_all_periods_ranked() -> pd.DataFrame:
    """
    Main rankings logic covering all symbols across five periods, with hourly caching.
    """
    today_hour = datetime.datetime.now().strftime('%Y-%m-%d %H')
    if global_cache['date'] == today_hour and global_cache['df_all_periods'] is not None:
        return global_cache['df_all_periods']
        
    business_days = get_nyse_business_days_comparison()
    if not business_days:
        return pd.DataFrame()
        
    symbols = get_all_tickers()
    if not symbols:
        return pd.DataFrame()
        
    all_dfs = []
    periods = [
        ('Daily', 'Daily'),
        ('1 Week', '1 Week'),
        ('2 Weeks', '2 Weeks'),
        ('1 Month', '1 Month'),
        ('2 Months', '2 Months')
    ]
    
    # Vectorized Math.erf normal survival function at 0 helper
    erf_vec = np.vectorize(math.erf)
    
    for period_name, period_key in periods:
        ndays_range = get_ndays_for_period(period_key, business_days)
        df_all = df_secind_sym_perf(ndays_range, symbols, business_days)
        
        if df_all.empty:
            continue
            
        # Sector / Industry relative strength
        ind_mean_pc = df_all.groupby(['sector', 'industry'])['over_pc'].transform('mean')
        df_all['rel_strength_ind'] = df_all['over_pc'] - ind_mean_pc
        
        mask_std_gt_0 = df_all['pc_std'].notna() & (df_all['pc_std'] > 0)
        
        # Calculate prob_green_day_% using erf: 50 * (1 + erf(mean / (std * sqrt(2))))
        df_all['prob_green_day_%'] = 0.0
        if mask_std_gt_0.any():
            means = df_all.loc[mask_std_gt_0, 'pc_mean']
            stds = df_all.loc[mask_std_gt_0, 'pc_std']
            df_all.loc[mask_std_gt_0, 'prob_green_day_%'] = 50.0 * (1.0 + erf_vec(means / (stds * math.sqrt(2.0))))
            
        # Stretch score: over_pc / std
        df_all['stretch_score'] = 0.0
        if mask_std_gt_0.any():
            df_all.loc[mask_std_gt_0, 'stretch_score'] = df_all.loc[mask_std_gt_0, 'over_pc'] / df_all.loc[mask_std_gt_0, 'pc_std']
            
        # Kelly Fraction: mean / std^2
        df_all['kelly_fraction'] = 0.0
        if mask_std_gt_0.any():
            df_all.loc[mask_std_gt_0, 'kelly_fraction'] = df_all.loc[mask_std_gt_0, 'pc_mean'] / (df_all.loc[mask_std_gt_0, 'pc_std'] ** 2)
            
        # Compute Ranks
        df_all['risk_reward_rank'] = df_all['risk_reward'].rank(ascending=False, method='min')
        df_all['rel_strength_ind_rank'] = df_all['rel_strength_ind'].rank(ascending=False, method='min')
        df_all['prob_green_day_rank'] = df_all['prob_green_day_%'].rank(ascending=False, method='min')
        df_all['stretch_score_rank'] = df_all['stretch_score'].rank(ascending=False, method='min')
        df_all['kelly_fraction_rank'] = df_all['kelly_fraction'].rank(ascending=False, method='min')
        
        # Period descriptors
        df_all['Period'] = period_name
        
        # Get actual date ranges for this period
        if len(ndays_range) >= 2:
            date_newest = business_days[ndays_range[-1]] if ndays_range[-1] < len(business_days) else 'Unknown'
            date_oldest = business_days[ndays_range[0]] if ndays_range[0] < len(business_days) else 'Unknown'
            # Format as MMM D, e.g. "Jun 2" or "Feb 23"
            try:
                dt_old = datetime.datetime.strptime(date_oldest, '%Y-%m-%d')
                dt_new = datetime.datetime.strptime(date_newest, '%Y-%m-%d')
                df_all['Date Range'] = f"{dt_old.strftime('%b %-d')} to {dt_new.strftime('%b %-d')}"
            except Exception:
                df_all['Date Range'] = f"{date_oldest} to {date_newest}"
        else:
            df_all['Date Range'] = "N/A"
            
        all_dfs.append(df_all)
        
    if not all_dfs:
        return pd.DataFrame()
        
    df_concat = pd.concat(all_dfs, ignore_index=True)
    global_cache['date'] = today_hour
    global_cache['df_all_periods'] = df_concat
    return df_concat
