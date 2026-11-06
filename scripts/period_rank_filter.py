import pandas as pd
from database.sqlite_connection import get_sqlite_conn
from portfolio.ticker_period_ranks_data import get_all_periods_ranked
from utils.ticker_reader import get_all_tickers
df_all_periods = get_all_periods_ranked(daily_step=True)
ticker = get_all_tickers()[0]
ticker_df = df_all_periods[df_all_periods['ticker'] == ticker]['Date Range']
first_date,second_date,third_date,fourth_date, fifth_date = ticker_df.iloc[0],ticker_df.iloc[1],ticker_df.iloc[2],ticker_df.iloc[3],ticker_df.iloc[4]
#print(first_date,second_date,third_date,fourth_date, fifth_date, sep = ',')
#print(ticker_df)

def df_filter_on_date_range(df_subset, rrr, rsir, ssr, kfr):
    distinct_dates = df_subset['Date Range'].unique().tolist()
    print(distinct_dates[0].split(" to ")[0], ' to ',distinct_dates[-1].split(" to ")[1],end=', ')
    #print(split_dates[0], split_dates[1], sep=", ", end=', ')
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
    
    #print(f"Lengths rrr= {rrr_len}, rsir= {rsir_len} ssr= {ssr_len} kfr= {kfr_len}", end=', ')
    common_tickers = set(rrr_tickers) & set(rsir_tickers) & set(ssr_tickers) & set(kfr_tickers)
    final_ticker_list = sorted(list(common_tickers))
    print(*final_ticker_list)
    return final_ticker_list

dates_filters = [[first_date],[first_date, second_date],[first_date, second_date, third_date],[first_date, second_date, third_date,fourth_date],[first_date, second_date, third_date,fourth_date, fifth_date]]

rrr = 100
rsir = 40
ssr = 150
kfr = 500

for date_filter in dates_filters:
    df_in_subset = df_all_periods[df_all_periods['Date Range'].isin(date_filter)]
    filtered_ticker_list = df_filter_on_date_range(df_in_subset, rrr, rsir, ssr, kfr)