import pandas as pd
from database.sqlite_connection import get_sqlite_conn, init_sqlite_db
from portfolio.ticker_period_ranks_data import get_all_periods_ranked
from utils.calendar_utils import get_busdate_ndays_ago, get_ndays_for_end
from utils.period_rank_utils import (
    ordinal,
    has_period_rank_results as _has_period_rank_results,
    save_period_rank_results as _save_period_rank_results,
    get_period_rank_results as _get_period_rank_results,
)


def has_period_rank_results(date_str: str) -> bool:
    return _has_period_rank_results(date_str, conn_fn=get_sqlite_conn)


def save_period_rank_results(rows: list):
    return _save_period_rank_results(rows, conn_fn=get_sqlite_conn)


def get_period_rank_results(date_str: str | None = None) -> pd.DataFrame:
    if date_str is None:
        date_str = get_busdate_ndays_ago(get_ndays_for_end())
    return _get_period_rank_results(date_str=date_str, conn_fn=get_sqlite_conn)


def df_filter_on_date_range(df_subset, rrr, rsir, ssr, kfr):
    distinct_dates = df_subset['Date Range'].unique().tolist()
    filtered_df = df_subset.groupby('ticker').filter(lambda x: (x['risk_reward_rank'] < rrr).all())
    rrr_tickers = sorted(list(set(filtered_df['ticker'].values)))
    rrr_len = len(rrr_tickers)
    filtered_df = df_subset.groupby('ticker').filter(lambda x: (x['rel_strength_ind_rank'] < rsir).all())
    rsir_tickers = sorted(list(set(filtered_df['ticker'].values)))
    rsir_len = len(rsir_tickers)
    filtered_df = df_subset.groupby('ticker').filter(lambda x: (x['stretch_score_rank'] < ssr).all())
    ssr_tickers = sorted(list(set(filtered_df['ticker'].values)))
    ssr_len = len(ssr_tickers)
    filtered_df = df_subset.groupby('ticker').filter(lambda x: (x['kelly_fraction_rank'] < kfr).all())
    kfr_tickers = sorted(list(set(filtered_df['ticker'].values)))
    kfr_len = len(kfr_tickers)
    # print(f"Lengths rrr= {rrr_len}, rsir= {rsir_len} ssr= {ssr_len} kfr= {kfr_len}")
    # print(distinct_dates[-1].split(" to ")[0], ' to ',distinct_dates[0].split(" to ")[1],end=', ')
    common_tickers = set(rrr_tickers) & set(rsir_tickers) & set(ssr_tickers) & set(kfr_tickers)
    final_ticker_list = sorted(list(common_tickers))
    print(*final_ticker_list)
    return final_ticker_list


def run_period_rank_filter(df_all_periods: pd.DataFrame | None = None) -> list:
    if df_all_periods is None:
        df_all_periods = get_all_periods_ranked(daily_step=True)
    if df_all_periods.empty:
        return []

    date_str = df_all_periods['date'].iloc[0]
    date_ranges = df_all_periods['Date Range'].unique().tolist()
    dates_filters = [date_ranges[:i] for i in range(1, len(date_ranges) + 1)]

    rsir = 40
    ssr = 150
    kfr = 500

    rows_to_insert = []
    for date_filter in dates_filters:
        step_label = ordinal(len(date_filter))
        print(step_label, end=', ')
        df_in_subset = df_all_periods[df_all_periods['Date Range'].isin(date_filter)]
        if len(date_filter) > 3:
            rrr = 175
        else:
            rrr = 70
        filtered_ticker_list = df_filter_on_date_range(df_in_subset, rrr, rsir, ssr, kfr)

        span_start = date_filter[-1].split(" to ")[0]
        span_end = date_filter[0].split(" to ")[-1]
        combined_date_range = f"{span_start} to {span_end}"
        tickers_str = " ".join(filtered_ticker_list)

        rows_to_insert.append((date_str, step_label, combined_date_range, tickers_str))

    if not has_period_rank_results(date_str):
        save_period_rank_results(rows_to_insert)
    return rows_to_insert


if __name__ == "__main__":
    run_period_rank_filter()
