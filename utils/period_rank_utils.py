import pandas as pd
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from utils.calendar_utils import get_busdate_ndays_ago, get_ndays_for_end
from utils.email_utils import DEFAULT_RECIPIENT_EMAIL, send_email


def ordinal(n: int) -> str:
    """Formats an integer `n` with its English ordinal suffix ('1st', '2nd', '3rd', etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def has_period_rank_results(date_str: str, conn_fn=None) -> bool:
    """
    Returns True if rows for `date_str` already exist in `period_rank_filter`.
    """
    init_sqlite_db()
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM period_rank_filter WHERE date = ?", (date_str,))
        row = cursor.fetchone()
        return bool(row and row[0] > 0)


def save_period_rank_results(rows: list, conn_fn=None):
    """
    Saves period rank filter results to the SQLite `period_rank_filter` table
    if no results exist yet for that date.
    Each tuple in `rows` is (date, period_step, date_range, tickers).
    """
    if not rows:
        return
    date_str = rows[0][0]
    if has_period_rank_results(date_str, conn_fn=conn_fn):
        return

    init_sqlite_db()
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO period_rank_filter (
                date,
                period_step,
                date_range,
                tickers
            )
            VALUES (?, ?, ?, ?)
        """, rows)


def get_period_rank_results(date_str: str | None = None, conn_fn=None) -> pd.DataFrame:
    """
    Retrieves rows from `period_rank_filter` for the given `date_str`
    (defaults to the last NYSE business date in YYYY-MM-DD format).
    """
    init_sqlite_db()
    if date_str is None:
        date_str = get_busdate_ndays_ago(get_ndays_for_end())

    query = """
        SELECT date, period_step, date_range, tickers
        FROM period_rank_filter
        WHERE date = ?
        ORDER BY CAST(period_step AS INTEGER)
    """
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        df = pd.read_sql_query(query, conn, params=(date_str,))
        if df.empty and date_str != get_busdate_ndays_ago(0):
            df = pd.read_sql_query(query, conn, params=(get_busdate_ndays_ago(0),))
    return df


def format_period_rank_results(df: pd.DataFrame) -> str:
    """Formats the `period_rank_filter` changes or results DataFrame into a readable text body."""
    if df.empty:
        return "No period_rank_filter records found."

    lines = []
    if "added" in df.columns and "missing" in df.columns:
        latest_date = df.attrs.get("latest_date")
        previous_date = df.attrs.get("previous_date")
        if latest_date and previous_date:
            lines.append(f"Comparing {latest_date} against {previous_date}:")
        for _, row in df.iterrows():
            added_str = row["added"] if row["added"] else "None"
            removed_str = row["missing"] if row["missing"] else "None"
            lines.append(f"{row['period_step']} | Added: {added_str} | Removed: {removed_str}")
        return "\n".join(lines)

    for _, row in df.iterrows():
        lines.append(f"{row['date']} | {row['period_step']} ({row['date_range']}): {row['tickers']}")
    return "\n".join(lines)


def analyze_period_step_ticker_changes(conn_fn=None) -> pd.DataFrame:
    """
    Queries the database for the last two distinct dates, aggregates tickers 
    by period_step, computes set differences (added and missing/removed), and 
    displays the results in a formatted presentation.
    """
    init_sqlite_db()
    _get_conn = conn_fn or get_sqlite_conn
    with _get_conn() as conn:
        # Get the two most recent dates in descending order
        dates_query = """
            SELECT DISTINCT date 
            FROM period_rank_filter 
            ORDER BY date DESC 
            LIMIT 2
        """
        dates_df = pd.read_sql_query(dates_query, conn)
        
        if len(dates_df) < 2:
            print("Error: Fewer than two dates available in the database.")
            return pd.DataFrame()
        
        latest_date = dates_df.iloc[0]['date']
        previous_date = dates_df.iloc[1]['date']
        print(f"Comparing latest date ({latest_date}) against previous date ({previous_date})...\n")
        
        # Fetch records for both dates
        data_query = """
            SELECT date, period_step, tickers 
            FROM period_rank_filter 
            WHERE date IN (?, ?)
            ORDER BY CAST(period_step AS INTEGER)
        """
        df = pd.read_sql_query(data_query, conn, params=[latest_date, previous_date])

    # Combine tickers across any matching period_steps if rows are split by date_range, 
    # or group directly by period_step and date.
    # Here we aggregate all ticker strings per period_step and date.
    def combine_tickers(series):
        all_words = []
        for val in series.dropna():
            all_words.extend(val.split())
        return set(all_words)

    grouped = df.groupby(['date', 'period_step'], sort=False)['tickers'].apply(combine_tickers).unstack(level=0)
    
    # Ensure both date columns exist
    if latest_date not in grouped.columns or previous_date not in grouped.columns:
        print("Error: Missing data for one of the dates in specific period steps.")
        return pd.DataFrame()

    presentation_results = []

    for period_step in grouped.index:
        latest_val = grouped.loc[period_step, latest_date]
        prev_val = grouped.loc[period_step, previous_date]
        latest_set = latest_val if isinstance(latest_val, set) else set()
        prev_set = prev_val if isinstance(prev_val, set) else set()

        # Added: present in latest but not previous
        added = sorted(list(latest_set - prev_set))
        # Missing (removed): present in previous but not latest
        missing = sorted(list(prev_set - latest_set))

        presentation_results.append({
            'period_step': period_step,
            'added': " ".join(added) if added else "",
            'missing': " ".join(missing) if missing else ""
        })

    result_df = pd.DataFrame(presentation_results)
    result_df.attrs["latest_date"] = latest_date
    result_df.attrs["previous_date"] = previous_date
    return result_df


def send_period_rank_email(
    df: pd.DataFrame | None = None,
    to_email: str = DEFAULT_RECIPIENT_EMAIL,
    sender_email: str | None = None,
    app_password: str | None = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 465,
    conn_fn=None,
):
    """
    Formats the period rank filter ticker changes (added and removed between the
    last two business dates) and sends them via `send_email`.
    """
    if df is None:
        df = analyze_period_step_ticker_changes(conn_fn=conn_fn)

    latest_date = df.attrs.get("latest_date")
    previous_date = df.attrs.get("previous_date")
    if latest_date and previous_date:
        subject = f"Period Rank Filter Changes - {latest_date} vs {previous_date}"
    elif not df.empty and "date" in df.columns:
        subject = f"Period Rank Filter Results - {df['date'].iloc[0]}"
    else:
        date_label = get_busdate_ndays_ago(get_ndays_for_end())
        subject = f"Period Rank Filter Changes - {date_label}"

    body = format_period_rank_results(df)

    return send_email(
        subject=subject,
        body=body,
        to_email=to_email,
        sender_email=sender_email,
        app_password=app_password,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
    )


if __name__ == "__main__":
    df_changes = analyze_period_step_ticker_changes()
    print(format_period_rank_results(df_changes))
    if not df_changes.empty:
        send_period_rank_email(df_changes, to_email=DEFAULT_RECIPIENT_EMAIL)
