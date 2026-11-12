import sqlite3
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from scripts.period_rank_filter import (
    ordinal,
    df_filter_on_date_range,
    has_period_rank_results,
    save_period_rank_results,
    run_period_rank_filter,
    get_period_rank_results,
)
from utils.period_rank_utils import (
    analyze_period_step_ticker_changes,
    send_period_rank_email,
)


def test_ordinal():
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(4) == "4th"
    assert ordinal(5) == "5th"
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"
    assert ordinal(21) == "21st"


def test_run_period_rank_filter_and_sqlite_persistence():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE period_rank_filter (
            date TEXT NOT NULL,
            period_step TEXT NOT NULL,
            date_range TEXT,
            tickers TEXT NOT NULL,
            PRIMARY KEY (date, period_step)
        )
    """)
    conn.commit()

    @contextmanager
    def _get_conn():
        yield conn
        conn.commit()

    periods = [
        ("Daily", "Oct 20 to Nov 3"),
        ("1 Week", "Sep 22 to Nov 3"),
        ("2 Weeks", "Aug 11 to Nov 3"),
        ("1 Month", "May 4 to Nov 3"),
        ("2 Months", "Nov 3 to Nov 3"),
    ]
    rows = []
    for period_name, d_range in periods:
        # AAPL passes all thresholds across all 5 periods
        rows.append({
            "ticker": "AAPL",
            "Period": period_name,
            "date": "2026-11-06",
            "Date Range": d_range,
            "risk_reward_rank": 10,
            "rel_strength_ind_rank": 5,
            "stretch_score_rank": 20,
            "kelly_fraction_rank": 50,
        })
        # MSFT has risk_reward_rank=100 (fails rrr=70 for steps 1..3, passes rrr=175 if all steps pass)
        rows.append({
            "ticker": "MSFT",
            "Period": period_name,
            "date": "2026-11-06",
            "Date Range": d_range,
            "risk_reward_rank": 100,
            "rel_strength_ind_rank": 10,
            "stretch_score_rank": 30,
            "kelly_fraction_rank": 60,
        })

    df_mock = pd.DataFrame(rows)

    with patch("scripts.period_rank_filter.get_sqlite_conn", _get_conn), \
         patch("scripts.period_rank_filter.init_sqlite_db"):
        inserted = run_period_rank_filter(df_all_periods=df_mock)

    assert len(inserted) == 5

    cursor.execute("SELECT date, period_step, date_range, tickers FROM period_rank_filter ORDER BY period_step")
    db_rows = cursor.fetchall()
    assert len(db_rows) == 5

    by_step = {r[1]: (r[0], r[2], r[3]) for r in db_rows}
    # Step 1st..3rd use rrr=70 -> only AAPL
    assert by_step["1st"] == ("2026-11-06", "Oct 20 to Nov 3", "AAPL")
    assert by_step["2nd"] == ("2026-11-06", "Sep 22 to Nov 3", "AAPL")
    assert by_step["3rd"] == ("2026-11-06", "Aug 11 to Nov 3", "AAPL")
    # Step 4th..5th use rrr=175 -> both AAPL and MSFT
    assert by_step["4th"] == ("2026-11-06", "May 4 to Nov 3", "AAPL MSFT")
    assert by_step["5th"] == ("2026-11-06", "Nov 3 to Nov 3", "AAPL MSFT")

    with patch("scripts.period_rank_filter.get_sqlite_conn", _get_conn), \
         patch("scripts.period_rank_filter.init_sqlite_db"), \
         patch("scripts.period_rank_filter.get_busdate_ndays_ago", return_value="2026-11-06"), \
         patch("scripts.period_rank_filter.get_ndays_for_end", return_value=0):
        df_retrieved = get_period_rank_results()
        assert len(df_retrieved) == 5
        assert list(df_retrieved["period_step"]) == ["1st", "2nd", "3rd", "4th", "5th"]
        assert df_retrieved.iloc[0]["date"] == "2026-11-06"
        assert df_retrieved.iloc[0]["tickers"] == "AAPL"
        assert df_retrieved.iloc[3]["tickers"] == "AAPL MSFT"

        # Verify has_period_rank_results is True for 2026-11-06 and False for another date
        assert has_period_rank_results("2026-11-06") is True
        assert has_period_rank_results("2026-11-05") is False

        # Verify calling save_period_rank_results again for existing date does not overwrite
        save_period_rank_results([("2026-11-06", "1st", "Oct 20 to Nov 3", "OVERWRITTEN")])
        df_after = get_period_rank_results()
        assert df_after.iloc[0]["tickers"] == "AAPL"

        # Insert a previous date (2026-11-05) to test analyze_period_step_ticker_changes
        save_period_rank_results([
            ("2026-11-05", "1st", "Oct 19 to Nov 2", "AAPL NVDA"),
            ("2026-11-05", "2nd", "Sep 21 to Nov 2", "AAPL"),
            ("2026-11-05", "3rd", "Aug 10 to Nov 2", "AAPL"),
            ("2026-11-05", "4th", "May 3 to Nov 2", "AAPL"),
            ("2026-11-05", "5th", "Nov 2 to Nov 2", "AAPL MSFT TSLA"),
        ])

        df_changes = analyze_period_step_ticker_changes(conn_fn=_get_conn)
        assert len(df_changes) == 5
        assert df_changes.attrs["latest_date"] == "2026-11-06"
        assert df_changes.attrs["previous_date"] == "2026-11-05"

        changes_by_step = {
            r["period_step"]: (r["added"], r["missing"])
            for _, r in df_changes.iterrows()
        }
        # 1st: 2026-11-06 has AAPL; 2026-11-05 had AAPL NVDA -> added="", missing="NVDA"
        assert changes_by_step["1st"] == ("", "NVDA")
        # 4th: 2026-11-06 has AAPL MSFT; 2026-11-05 had AAPL -> added="MSFT", missing=""
        assert changes_by_step["4th"] == ("MSFT", "")
        # 5th: 2026-11-06 has AAPL MSFT; 2026-11-05 had AAPL MSFT TSLA -> added="", missing="TSLA"
        assert changes_by_step["5th"] == ("", "TSLA")

        # Verify send_period_rank_email formats and sends ticker changes email to philip.massey@gmail.com
        with patch("utils.email_utils.smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            msg = send_period_rank_email(app_password="test-app-password", conn_fn=_get_conn)
            assert msg["To"] == "philip.massey@gmail.com"
            assert "2026-11-06 vs 2026-11-05" in msg["Subject"]
            body = msg.get_content()
            assert "1st | Added: None | Removed: NVDA" in body
            assert "4th | Added: MSFT | Removed: None" in body
            mock_server.send_message.assert_called_once_with(msg)

    conn.close()

