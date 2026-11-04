from datetime import datetime, timedelta
from typing import List
from dateutil.relativedelta import relativedelta
import numpy as np
import pytz
import pandas_market_calendars as mcal

nyse = mcal.get_calendar('NYSE')


def get_ny_now():
    """Returns current Eastern Time (America/New_York) as a naive datetime."""
    return datetime.now(pytz.timezone('America/New_York')).replace(tzinfo=None)


def get_busdate_ndays_ago(ndays: int) -> str:
    """Returns the NYSE business date string (YYYY-MM-DD) `ndays` business days ago."""
    strdate = '{:%Y-%m-%d}'.format(get_ny_now())
    dt = np.busday_offset(dates=strdate, offsets=-ndays, roll='backward', holidays=nyse.holidays().holidays)
    return str(dt)


def get_ndays_for_end() -> int:
    """Returns 1 if today is a valid NYSE trading day, 0 otherwise."""
    today = f'{get_ny_now():%Y-%m-%d}'
    days = nyse.valid_days(start_date=today, end_date=today)
    return len(days)


def get_nbusdays_from_date(date) -> int:
    """Counts NYSE business days between `date` and today (rolled backward)."""
    datestr = f'{date:%Y-%m-%d}'
    dtnow = '{:%Y-%m-%d}'.format(get_ny_now())
    bus_dtnow = np.busday_offset(dates=dtnow, offsets=0, roll='backward', holidays=nyse.holidays().holidays)
    dt = str(bus_dtnow)
    nbdays = np.busday_count(datestr, dt, holidays=nyse.holidays().holidays)
    return int(nbdays)


def get_ndays_periods(months=None, weeks=None, days=None):
    """Calculates discrete NYSE business-day period lookback offsets."""
    if months is None:
        months = []
    if weeks is None:
        weeks = []
    if days is None:
        days = []
    last_day = int(get_ndays_for_end())
    now = get_ny_now()
    periods: list[int] = []
    for idx in months:
        periods.append(get_nbusdays_from_date(now - relativedelta(months=idx)))
    for idx in weeks:
        periods.append(get_nbusdays_from_date(now - relativedelta(weeks=idx)))
    for idx in days:
        periods.append(get_nbusdays_from_date(now - relativedelta(days=idx)))
    if len(days) == 0:
        periods.append(last_day)
    periods = sorted(list(set(periods)), reverse=True)
    return tuple(periods)


def get_ndays_periods_step(
    months=None,
    weeks=None,
    days=None,
    busdays=None,
    daily_step=True,
    ndays_for_end_fn=None,
    nbusdays_from_date_fn=None,
    ny_now_fn=None,
):
    """Calculates business-day period offsets for multi-period return analysis.

    Args:
        months: List/tuple of month lookbacks
        weeks: List/tuple of week lookbacks (e.g., [12, 0])
        days: List/tuple of calendar day lookbacks
        busdays: Exact count of business days to look back (recommended)
        daily_step: If True, generates consecutive business days from max lookback
          down to last_day, maximizing sample size N for robust volatility and
          Kelly calculations. If False, samples only at the discrete milestone
          intervals.

    Returns:
        tuple of descending business-day offsets ending at last_day.
    """
    _get_ndays_for_end = ndays_for_end_fn or get_ndays_for_end
    _get_nbusdays_from_date = nbusdays_from_date_fn or get_nbusdays_from_date
    _get_ny_now = ny_now_fn or get_ny_now

    last_day = _get_ndays_for_end()
    now = _get_ny_now()
    raw_periods = []

    # 1. Determine the maximum lookback in business days
    if busdays is not None:
        max_busdays = busdays if isinstance(busdays, int) else max(busdays)
        raw_periods.append(max_busdays)

    if months:
        for idx in months:
            target_date = now - relativedelta(months=idx)
            raw_periods.append(_get_nbusdays_from_date(target_date))

    if weeks:
        for idx in weeks:
            target_date = now - relativedelta(weeks=idx)
            raw_periods.append(_get_nbusdays_from_date(target_date))

    if days:
        for idx in days:
            target_date = now - relativedelta(days=idx)
            raw_periods.append(_get_nbusdays_from_date(target_date))

    # Ensure last_day is present
    raw_periods.append(last_day)
    raw_periods = sorted(list(set(raw_periods)), reverse=True)

    # 2. Daily sampling within the window (Maximizes degrees of freedom)
    if daily_step:
        earliest_day = raw_periods[0]
        # Consecutive business day sequence from earliest_day down to last_day
        return tuple(range(earliest_day, last_day - 1, -1))

    # 3. Discrete interval sampling (Preserves stepped milestones)
    return tuple(raw_periods)


def get_date_for_mdb(ndays: int) -> datetime:
    """Returns a datetime object for the NYSE business date `ndays` ago."""
    strDate = get_busdate_ndays_ago(ndays)
    return datetime.strptime(strDate, '%Y-%m-%d')


def get_date_for_ndays(ndays: int) -> str:
    """Returns a formatted date string ('%b %-d') for `ndays` business days ago."""
    dt = get_date_for_mdb(ndays)
    return f'{dt:%b %-d}'


def get_mdbdate_from_strdate(strDate: str) -> datetime:
    """Parses a 'YYYY-MM-DD' date string into a datetime object."""
    return datetime.strptime(strDate, '%Y-%m-%d')


def get_nyse_calendar_past_year() -> List[str]:
    """
    Returns a list of NYSE trading days (YYYY-MM-DD) for the past 1 year,
    ending on the most recent previous business day.
    """
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
