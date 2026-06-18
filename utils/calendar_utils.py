from datetime import datetime, timedelta
from typing import List
import pytz
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

def get_nyse_business_days_comparison() -> List[str]:
    """
    Returns a list of NYSE business days (strings in YYYY-MM-DD format)
    from the latest NYSE trading day back to one year before it,
    based on the NYSE valid days.
    """
    nyse = mcal.get_calendar('NYSE')
    today = datetime.now(pytz.timezone("America/New_York")).date()
    schedule = nyse.valid_days(
        start_date=(today - timedelta(days=370)).strftime('%Y-%m-%d'),
        end_date=today.strftime('%Y-%m-%d')
    )
    
    if len(schedule) == 0:
        return []
        
    # to_date: last completed NYSE trading day
    to_date = schedule[-1].date()

    # from_date: most recent trading day on or before one year before to_date
    one_year_ago = to_date.replace(year=to_date.year - 1)
    
    past_dates = [d.date() for d in schedule if d.date() <= one_year_ago]
    if not past_dates:
        from_date = schedule[0].date()
    else:
        from_date = max(past_dates)

    business_days = [d.date() for d in reversed(schedule) if from_date <= d.date() <= to_date]
    return [d.strftime('%Y-%m-%d') for d in business_days]

