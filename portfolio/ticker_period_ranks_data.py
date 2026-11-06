import math
import pandas as pd
import numpy as np
import os
import json
from os.path import isfile, join, isdir
from os import listdir
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from database.sqlite_connection import get_sqlite_conn
from database.database_utils import get_close_price_records

from utils.calendar_utils import (
    nyse,
    get_ny_now,
    get_busdate_ndays_ago,
    get_ndays_for_end,
    get_nbusdays_from_date,
    get_ndays_periods,
    get_date_for_mdb,
    get_date_for_ndays,
    get_mdbdate_from_strdate,
)

from utils.ticker_utils import (
    all,
    data_dir,
    portfolio_from_file,
    get_dir_port_tickers,
    get_port_and_tickers,
    get_tickers,
    get_tickers_dir_or_port,
    get_tickers_for_portfolios,
    get_portfolio_dirs,
    df_ticker_profile,
)

from portfolio.ticker_period_ranked_coarse import (
    calc_percent_year,
    calc_percent_2monthly,
    calc_percent_monthly,
    calc_percent_2weekly,
    calc_percent_weekly,
    calc_percent_daily,
    get_ndays_range_step,
)

global_cache = {
    'date': None,
    'df_all_periods': None,
    'cache_by_mode': {}
}


# ============ MARKET_DATA FUNCTIONS ============

def get_df_from_mdb_for_nday(ndays, coll_name, tickers='', incl='', dateidx=True):
    date_str = get_busdate_ndays_ago(ndays)
    if len(incl) != 0:
        tickers = get_tickers(incl)
    if not tickers:
        return pd.DataFrame({})

    records = get_close_price_records(tickers, [date_str])
    if not records:
        return pd.DataFrame({})

    df = pd.DataFrame(records)
    if dateidx:
        df.set_index('Date', inplace=True)
    return df


def df_mdb_clossins_for_ndays_range(ndays_range, tickers):
    if not tickers:
        return pd.DataFrame({})

    dates = [get_busdate_ndays_ago(ndays) for ndays in ndays_range]
    records = get_close_price_records(tickers, dates)
    if not records:
        return pd.DataFrame(columns=tickers)

    df_all = pd.DataFrame(records)
    df_all.set_index('Date', inplace=True)

    # Ensure all tickers exist as columns
    df_all = df_all.reindex(columns=tickers)

    return df_all


# ============ PERFORMANCE FUNCTIONS ============

def get_ndays_range(opt_ndays_range, daily_step=False):
    """
    Wrapper that can return either discrete milestones or explicit daily range steps
    depending on the `daily_step` flag.
    """
    if daily_step:
        return get_ndays_range_step(opt_ndays_range, daily_step=True)

    # Existing legacy discrete range logic
    if opt_ndays_range == calc_percent_2monthly:
        ndays_range = get_ndays_periods(months=list(range(12, 0, -2)))
    elif opt_ndays_range == calc_percent_monthly:
        ndays_range = get_ndays_periods(months=list(range(6, 0, -1)))
    elif opt_ndays_range == calc_percent_2weekly:
        ndays_range = get_ndays_periods(weeks=list(range(12, 0, -2)))
    elif opt_ndays_range == calc_percent_weekly:
        ndays_range = get_ndays_periods(weeks=list(range(6, 0, -1)))
    elif opt_ndays_range == calc_percent_year:
        ndays_range = get_ndays_periods(months=(12, 6, 3, 1), weeks=(2, 1))
    elif opt_ndays_range == calc_percent_daily:
        ndays_range = get_ndays_periods(days=list(range(10, 0, -1)))
    else:
        ndays_range = get_ndays_periods()

    return ndays_range


def df_overall_performance(ndays_range, tickers):
    """
    Calculate performance metrics for tickers over a given date range.
    
    Returns a DataFrame with the following calculated columns:
    - over_pc: The overall percentage change.
    - pc_mean: The average period-to-period percentage change.
    - pc_std:  The standard deviation (volatility) of the period changes.
    - risk_reward: The ratio of mean return to standard deviation.
    """
    df_all = df_mdb_clossins_for_ndays_range(ndays_range, tickers)

    if df_all.empty:
        return pd.DataFrame(columns=['ticker', 'over_pc', 'pc_mean', 'pc_std', 'risk_reward'])

    # Calculate overall percentage based on first valid and last valid price
    first_valid = df_all.bfill().iloc[0]
    last_valid = df_all.ffill().iloc[-1]
    df_over_pct = ((last_valid - first_valid) / first_valid) * 100

    df_vars = pd.DataFrame(df_over_pct, columns=['over_pc'])

    # Calculate period pct change but immediately drop NaNs so mean/std aren't poisoned
    df_period_pct = df_all.pct_change(periods=1) * 100

    # Calculate metric ignoring NaNs
    df_vars['pc_mean'] = df_period_pct.mean()
    df_vars['pc_std'] = df_period_pct.std()

    # Risk-Reward Proxy (Simplified Sharpe)
    df_vars['risk_reward'] = np.where(
        df_vars['pc_std'] != 0,
        df_vars['pc_mean'] / df_vars['pc_std'],
        0
    )

    df_vars.reset_index(inplace=True)
    df_vars.rename(columns={'index': 'ticker'}, inplace=True)
    df_vars = df_vars.round(3)
    return df_vars


def df_perc_by_sector_industry(ndays_range, tickers):
    fields = ['sectorname', 'primaryname', 'ticker']
    df = df_ticker_profile(tickers, fields)
    df.dropna(inplace=True)
    return df


def df_secind_tick_perf(ndays_range, tickers):
    """
    Combines sector and industry info with the performance metrics.
    Retrieves the metrics calculated in df_overall_performance (over_pc, pc_mean, pc_std, risk_reward).
    """
    df_over_perf = df_overall_performance(ndays_range, tickers)
    if df_over_perf.empty:
        return pd.DataFrame(columns=['sector', 'industry', 'ticker', 'over_pc', 'pc_mean', 'pc_std', 'risk_reward'])

    df_sector_ind = df_perc_by_sector_industry(ndays_range, tickers)
    df_sector_ind.rename(columns={'sectorname': 'sector', 'primaryname': 'industry'}, inplace=True)

    # Merge using a left join anchored on performance
    df_secind_tick_perf = df_over_perf.merge(df_sector_ind, on='ticker', how='left')

    # Handle NaNs from API mapping missing profiles
    df_secind_tick_perf['sector'] = df_secind_tick_perf['sector'].fillna('Unknown')
    df_secind_tick_perf['industry'] = df_secind_tick_perf['industry'].fillna('Unknown')

    cols = ['sector', 'industry', 'ticker', 'over_pc', 'pc_mean', 'pc_std', 'risk_reward']
    return df_secind_tick_perf[cols].sort_values(by=['sector', 'industry', 'ticker'])


def get_all_periods_ranked(daily_step=True):
    """
    Retrieve and calculate ranking metrics for all tickers across multiple time periods.
    Results are cached per hour to improve performance.
    
    Returns:
        pd.DataFrame: Combined dataframe with ranking data for all periods
    """
    today = datetime.now().strftime('%Y-%m-%d %H')  # Cache per hour
    if global_cache.get('date') != today:
        global_cache['date'] = today
        global_cache['cache_by_mode'] = {}
        global_cache['df_all_periods'] = None

    if daily_step in global_cache.get('cache_by_mode', {}):
        df_cached = global_cache['cache_by_mode'][daily_step]
        global_cache['df_all_periods'] = df_cached
        return df_cached

    tickers = get_tickers(all)
    all_dfs = []
    periods = [
        ('Daily', calc_percent_daily),
        ('1 Week', calc_percent_weekly),
        ('2 Weeks', calc_percent_2weekly),
        ('1 Month', calc_percent_monthly),
        ('2 Months', calc_percent_2monthly)
    ]

    for period_name, opt_val in periods:
        ndays_range = get_ndays_range(opt_val, daily_step)
        df_all = df_secind_tick_perf(ndays_range, tickers)
        if df_all.empty:
            continue

        # Calculate relative strength vs industry
        ind_mean_pc = df_all.groupby(['sector', 'industry'])['over_pc'].transform('mean')
        df_all['rel_strength_ind'] = df_all['over_pc'] - ind_mean_pc

        # Calculate probability of green day
        mask_std_gt_0 = df_all['pc_std'].notna() & (df_all['pc_std'] > 0)
        df_all['prob_green_day_%'] = 0.0
        if mask_std_gt_0.any():
            erf_vec = np.vectorize(math.erf)
            means = df_all.loc[mask_std_gt_0, 'pc_mean']
            stds = df_all.loc[mask_std_gt_0, 'pc_std']
            df_all.loc[mask_std_gt_0, 'prob_green_day_%'] = 50.0 * (1.0 + erf_vec(means / (stds * math.sqrt(2.0))))

        # Calculate stretch score
        df_all['stretch_score'] = 0.0
        df_all.loc[mask_std_gt_0, 'stretch_score'] = (
            df_all.loc[mask_std_gt_0, 'over_pc'] / df_all.loc[mask_std_gt_0, 'pc_std']
        )

        # Calculate Kelly fraction
        df_all['kelly_fraction'] = 0.0
        df_all.loc[mask_std_gt_0, 'kelly_fraction'] = (
            df_all.loc[mask_std_gt_0, 'pc_mean'] / (df_all.loc[mask_std_gt_0, 'pc_std'] ** 2)
        )

        # Calculate rankings
        df_all['risk_reward_rank'] = df_all['risk_reward'].rank(ascending=False, method='min')
        df_all['rel_strength_ind_rank'] = df_all['rel_strength_ind'].rank(ascending=False, method='min')
        df_all['prob_green_day_rank'] = df_all['prob_green_day_%'].rank(ascending=False, method='min')
        df_all['stretch_score_rank'] = df_all['stretch_score'].rank(ascending=False, method='min')
        df_all['kelly_fraction_rank'] = df_all['kelly_fraction'].rank(ascending=False, method='min')

        # Add period metadata
        df_all['Period'] = period_name
        date_newest = get_date_for_ndays(ndays_range[-1])
        date_oldest = get_date_for_ndays(ndays_range[0])
        df_all['Date Range'] = f"{date_oldest} to {date_newest}"

        all_dfs.append(df_all)

    if not all_dfs:
        return pd.DataFrame({})

    df_concat = pd.concat(all_dfs, ignore_index=True)
    global_cache['date'] = today
    if 'cache_by_mode' not in global_cache:
        global_cache['cache_by_mode'] = {}
    global_cache['cache_by_mode'][daily_step] = df_concat
    global_cache['df_all_periods'] = df_concat
    return df_concat


def filter_tickers_by_rank(df_all, rank_filter_value, min_periods=4):
    """
    Filter tickers based on rank filter and minimum number of periods with valid data.
    
    Args:
        df_all: Full dataframe from get_all_periods_ranked()
        rank_filter_value: Maximum rank value to include
        min_periods: Minimum number of periods a ticker must have data for
        
    Returns:
        pd.DataFrame: Filtered dataframe
    """
    if rank_filter_value is not None:
        df_all_filtered = df_all[df_all['risk_reward_rank'] <= rank_filter_value]
    else:
        df_all_filtered = df_all.copy()

    ticker_period_counts = df_all_filtered.groupby('ticker').size()
    valid_tickers = ticker_period_counts[ticker_period_counts >= min_periods].index.tolist()

    df_all = df_all[df_all['ticker'].isin(valid_tickers)]
    if rank_filter_value is not None:
        df_all = df_all[df_all['risk_reward_rank'] <= rank_filter_value]

    return df_all


def filter_by_portfolio(df_all, directory, port):
    """
    Filter dataframe to only include tickers from a specific portfolio.
    
    Args:
        df_all: Full dataframe from get_all_periods_ranked()
        directory: Portfolio directory
        port: Portfolio name
        
    Returns:
        pd.DataFrame: Filtered dataframe
    """
    if directory is not None:
        tickers = get_tickers_dir_or_port(directory=directory, port=port)
        df_all = df_all[df_all['ticker'].isin(tickers)]
    return df_all


def filter_by_sector_industry(df_all, sector, industry):
    """
    Filter dataframe by sector and/or industry.
    
    Args:
        df_all: Full dataframe from get_all_periods_ranked()
        sector: Sector name (optional)
        industry: Industry name (optional)
        
    Returns:
        pd.DataFrame: Filtered dataframe
    """
    if sector is not None and sector != '':
        df_all = df_all[df_all['sector'] == sector]
    if industry is not None and industry != '':
        df_all = df_all[df_all['industry'] == industry]
    return df_all


def get_ticker_period_data(df_all, ticker, rank_filter_value=None):
    """
    Get ranking data for a specific ticker across all periods.
    
    Args:
        df_all: Full dataframe from get_all_periods_ranked()
        ticker: Ticker to retrieve data for
        rank_filter_value: Maximum rank value to include (optional)
        
    Returns:
        pd.DataFrame: Filtered dataframe for the ticker
    """
    df_tick = df_all[df_all['ticker'] == ticker].copy()

    if rank_filter_value is not None:
        df_tick = df_tick[df_tick['risk_reward_rank'] <= rank_filter_value]

    return df_tick


def prepare_period_table_data(df_tick):
    """
    Prepare period table data for display, including column renaming and ordering.
    
    Args:
        df_tick: Ticker dataframe from get_ticker_period_data()
        
    Returns:
        pd.DataFrame: Formatted dataframe with period data
    """
    rename_dict = {
        'Period': 'Period', 'Date Range': 'Date Range',
        'over_pc': 'Over PC', 'pc_mean': 'PC Mean', 'pc_std': 'PC Std',
        'risk_reward_rank': 'Risk Reward Rank', 'rel_strength_ind_rank': 'Rel Strength Rank',
        'prob_green_day_rank': 'Prob Green Rank', 'stretch_score_rank': 'Stretch Score Rank',
        'kelly_fraction_rank': 'Kelly Rank'
    }

    df_tick = df_tick[list(rename_dict.keys())]
    df_tick.rename(columns=rename_dict, inplace=True)

    period_order = {'Daily': 1, '1 Week': 2, '2 Weeks': 3, '1 Month': 4, '2 Months': 5}
    df_tick['order'] = df_tick['Period'].map(period_order)
    df_tick.sort_values('order', inplace=True)
    df_tick.drop(columns=['order'], inplace=True)

    return df_tick


def prepare_ticker_table_data(df_all, period='1 Month', sector=None, industry=None):
    """
    Prepare ticker table data for display.
    
    Args:
        df_all: Full dataframe from get_all_periods_ranked()
        period: Period to filter by (default: '1 Month')
        sector: Sector to filter by (optional)
        industry: Industry to filter by (optional)
        
    Returns:
        pd.DataFrame: Formatted dataframe for ticker table
    """
    if period:
        df_period = df_all[df_all['Period'] == period]
    else:
        df_period = df_all[df_all['Period'] == '1 Month']

    df_unique = df_period[[
        'sector', 'industry', 'ticker',
        'risk_reward_rank', 'rel_strength_ind_rank',
        'stretch_score_rank', 'kelly_fraction_rank'
    ]].copy()

    df_unique = filter_by_sector_industry(df_unique, sector, industry)

    df_unique = df_unique.sort_values(by=['risk_reward_rank', 'sector', 'industry', 'ticker'])
    df_unique.rename(columns={'sector': 'Sector', 'industry': 'Industry', 'ticker': 'Ticker'}, inplace=True)

    return df_unique


def clear_cache():
    """
    Clear the global cache to force fresh data retrieval.
    """
    global_cache['date'] = None
    global_cache['df_all_periods'] = None
    global_cache['cache_by_mode'] = {}
