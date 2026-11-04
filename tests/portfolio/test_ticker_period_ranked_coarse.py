import pytest
from unittest.mock import patch
from portfolio.ticker_period_ranked_coarse import (
    get_ndays_periods_step,
    get_ndays_range,
    get_ndays_range_step,
)
from portfolio.ticker_period_ranks_data import (
    calc_percent_daily,
    calc_percent_weekly,
    calc_percent_2weekly,
    calc_percent_monthly,
    calc_percent_2monthly,
    calc_percent_year,
    get_all_periods_ranked,
    clear_cache,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_get_ndays_periods_step_daily_step():
    with patch('portfolio.ticker_period_ranked_coarse.get_ndays_for_end', return_value=0), \
         patch('portfolio.ticker_period_ranked_coarse.get_nbusdays_from_date', return_value=10):
        # With busdays=10 and daily_step=True
        periods = get_ndays_periods_step(busdays=10, daily_step=True)
        assert isinstance(periods, tuple)
        # Should generate consecutive steps: 10, 9, 8, ..., 0
        assert periods == tuple(range(10, -1, -1))


def test_get_ndays_periods_step_discrete():
    with patch('portfolio.ticker_period_ranked_coarse.get_ndays_for_end', return_value=0), \
         patch('portfolio.ticker_period_ranked_coarse.get_nbusdays_from_date', side_effect=[60, 30]):
        # With discrete sampling
        periods = get_ndays_periods_step(weeks=[12, 6], daily_step=False)
        assert isinstance(periods, tuple)
        assert periods[0] >= periods[-1]
        assert 0 in periods  # last_day


def test_get_ndays_range_mappings():
    # Test all period constants map without error
    options = [
        calc_percent_daily,
        calc_percent_weekly,
        calc_percent_2weekly,
        calc_percent_monthly,
        calc_percent_2monthly,
        calc_percent_year,
    ]
    for opt in options:
        r_step = get_ndays_range(opt, daily_step=True)
        assert isinstance(r_step, tuple)
        assert len(r_step) > 0

        r_discrete = get_ndays_range(opt, daily_step=False)
        assert isinstance(r_discrete, tuple)
        assert len(r_discrete) > 0


def test_get_all_periods_ranked_with_daily_step():
    import pandas as pd
    mock_perf_df = pd.DataFrame([
        {
            'sector': 'Technology',
            'industry': 'Software',
            'ticker': 'AAPL',
            'over_pc': 2.5,
            'pc_mean': 0.5,
            'pc_std': 1.2,
            'risk_reward': 0.42
        }
    ])

    with patch('portfolio.ticker_period_ranks_data.get_tickers', return_value=['AAPL']), \
         patch('portfolio.ticker_period_ranks_data.df_secind_tick_perf', side_effect=lambda *a, **k: mock_perf_df.copy()), \
         patch('portfolio.ticker_period_ranks_data.get_date_for_ndays', return_value='Oct 1'):

        df_ranked = get_all_periods_ranked(daily_step=True)
        assert not df_ranked.empty
        assert 'risk_reward_rank' in df_ranked.columns
        assert len(df_ranked) == 5  # 5 periods * 1 ticker
