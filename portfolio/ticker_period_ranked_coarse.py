import os
import sys
import math
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np

from utils.calendar_utils import (
    get_ndays_periods,
    get_nbusdays_from_date,
    get_ny_now,
    get_ndays_for_end,
    get_ndays_periods_step as _get_ndays_periods_step,
)

# Constants shared with ticker_period_ranks_data
calc_percent_year = '1_year'
calc_percent_2monthly = '2_monthly'
calc_percent_monthly = '1_monthly'
calc_percent_2weekly = '2_week'
calc_percent_weekly = '1_week'
calc_percent_daily = '1_day'

global_cache = {
    'date': None,
    'df_all_periods': None
}


def clear_cache():
    """
    Clear the global cache to force fresh data retrieval.
    """
    global_cache['date'] = None
    global_cache['df_all_periods'] = None


def get_ndays_periods_step(
    months=None, weeks=None, days=None, busdays=None, daily_step=True
):
    """Calculates business-day period offsets for multi-period return analysis."""
    return _get_ndays_periods_step(
        months=months,
        weeks=weeks,
        days=days,
        busdays=busdays,
        daily_step=daily_step,
        ndays_for_end_fn=get_ndays_for_end,
        nbusdays_from_date_fn=get_nbusdays_from_date,
        ny_now_fn=get_ny_now,
    )


def get_ndays_range(opt_ndays_range, daily_step=True):
    """Maps period options to optimized business-day offset ranges, supporting daily_step."""
    if opt_ndays_range == calc_percent_daily:
        return get_ndays_periods_step(busdays=10, daily_step=daily_step)
    elif opt_ndays_range == calc_percent_weekly:
        return get_ndays_periods_step(weeks=[6], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_2weekly:
        return get_ndays_periods_step(weeks=[12], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_monthly:
        return get_ndays_periods_step(months=[6], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_2monthly:
        return get_ndays_periods_step(months=[12], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_year:
        return get_ndays_periods_step(months=(12, 6, 3, 1), weeks=(2, 1), daily_step=daily_step)

    # Fallback default discrete interval sampling if option is unknown
    return get_ndays_periods_step(daily_step=daily_step)


def get_ndays_range_step(opt_ndays_range, daily_step=True):
    """Maps period options to optimized business-day offset ranges.

    Aligns windows to standard quantitative horizons:
      - calc_percent_daily:    10 business days (Tactical / Mean Reversion)
      - calc_percent_weekly:   21 business days (~1 month)
      - calc_percent_2weekly:  42 business days (~2 months)
      - calc_percent_monthly:  63 business days (~1 quarter / Early Momentum)
      - calc_percent_2monthly: 126 business days (~6 months / Core Momentum)
      - calc_percent_year:     252 business days (1 trading year)
    """
    if opt_ndays_range == calc_percent_daily:
        return get_ndays_periods_step(busdays=10, daily_step=True)
    elif opt_ndays_range == calc_percent_weekly:
        return get_ndays_periods_step(weeks=[6], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_2weekly:
        return get_ndays_periods_step(weeks=[12], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_monthly:
        return get_ndays_periods_step(months=[6], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_2monthly:
        return get_ndays_periods_step(months=[12], daily_step=daily_step)
    elif opt_ndays_range == calc_percent_year:
        return get_ndays_periods_step(months=[12], daily_step=daily_step)
