# pyrefly: ignore [missing-import]
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
        
    # Memorial Day 2026 was May 25, 2026 (market holiday)
    assert "2026-05-25" not in calendar
    
    # The days after Memorial Day 2026 (May 26th to 29th) should be trading days
    for day in ["2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29"]:
        assert day in calendar

