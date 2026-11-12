from utils.period_rank_utils import (
    DEFAULT_RECIPIENT_EMAIL,
    analyze_period_step_ticker_changes,
    format_period_rank_results,
    send_period_rank_email,
)


def main():
    df = analyze_period_step_ticker_changes()
    print(format_period_rank_results(df))
    if not df.empty:
        send_period_rank_email(df, to_email=DEFAULT_RECIPIENT_EMAIL)


if __name__ == "__main__":
    main()
