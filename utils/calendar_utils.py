from datetime import datetime, timedelta
from typing import List
import pandas_market_calendars as mcal

def get_nyse_calendar_past_year() -> List[str]:
    """
    Returns a list of NYSE trading days (YYYY-MM-DD) for the past 1 year,
    ending on the most recent previous business day.
    """
    nyse = mcal.get_calendar('NYSE')
    
    # End date is yesterday to ensure we don't grab partial/changing data for today
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=365)
    
    schedule = nyse.schedule(start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d'))
    
    # Convert index to a list of string dates 'YYYY-MM-DD'
    return [date.strftime('%Y-%m-%d') for date in schedule.index]
