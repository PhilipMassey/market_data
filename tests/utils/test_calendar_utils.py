import pytest
from datetime import datetime
from utils.calendar_utils import get_nyse_calendar_past_year

def test_get_nyse_calendar_past_year():
    calendar = get_nyse_calendar_past_year()
    assert isinstance(calendar, list)
    assert len(calendar) > 0
    for date_str in calendar:
        assert isinstance(date_str, str)
        # Should be 'YYYY-MM-DD'
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        assert dt is not None
