import os
from os.path import isfile, join, isdir
from os import listdir
import pandas as pd
from utils.ticker_reader import TICKERS_ROOT_DIRECTORY
from database.sqlite_connection import get_sqlite_conn

all = 'ALL'
data_dir = TICKERS_ROOT_DIRECTORY


def portfolio_from_file(subdir, file):
    path = join(data_dir, subdir, file)
    df = pd.read_csv(path)
    fname = file[0:-4]
    df['portfolio'] = fname
    df.rename(columns={'Symbol': 'ticker', 'Ticker': 'ticker', 'symbol': 'ticker'}, inplace=True)
    if 'ticker' in df.columns:
        df['ticker'] = df['ticker'].astype(str).str.strip().str.upper()
    return df


def get_dir_port_tickers(subdir):
    path = os.path.join(data_dir, subdir)
    csv_files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith('.csv')]
    dfall = pd.DataFrame(columns=('portfolio', 'ticker'))
    for file in csv_files:
        dfall = pd.concat([dfall, portfolio_from_file(subdir, file)], axis=0)
    dfall.reset_index(drop=True, inplace=True)
    return dfall


def get_port_and_tickers(directory):
    df_all = pd.DataFrame(columns=('portfolio', 'ticker'))
    if directory is None or directory == all:
        dirs = [d for d in listdir(data_dir) if isdir(join(data_dir, d))]
        for dir in dirs:
            df = get_dir_port_tickers(dir)
            df_all = pd.concat([df_all, df], axis=0)
    else:
        df = get_dir_port_tickers(directory)
        df_all = pd.concat([df_all, df], axis=0)
    return df_all


def get_tickers(directory='', ports=[]):
    if len(directory) > 0:
        df = get_port_and_tickers(directory)
        tickers = list(set(df.ticker.values))
    else:
        tickers = get_tickers_for_portfolios(ports)
    return tickers


def get_tickers_dir_or_port(directory, port):
    tickers = []
    if port is not None and len(port) > 0:
        tickers = get_tickers_for_portfolios([port])
    elif directory is not None:
        df = get_port_and_tickers(directory)
        tickers = list(set(df.ticker.values))
    else:
        tickers = []
    return tickers


def get_tickers_for_portfolios(portfolios):
    port_tickers = get_port_and_tickers(all)
    return list(port_tickers[port_tickers['portfolio'].isin(portfolios)].ticker.values)


def get_portfolio_dirs():
    if not os.path.exists(data_dir):
        return []
    return sorted(d for d in listdir(data_dir) if isdir(join(data_dir, d)))


def get_portfolios_in_dir(directory: str) -> list:
    target_dir = os.path.join(data_dir, directory)
    if not os.path.exists(target_dir):
        return []
    csv_files = [f for f in listdir(target_dir) if isfile(join(target_dir, f)) and f.endswith('.csv')]
    return sorted(os.path.splitext(f)[0] for f in csv_files)


def df_ticker_profile(tickers=[], fields=None):
    query = "SELECT ticker, sector, industry FROM ticker_meta_profile"
    params = []
    if tickers:
        placeholders = ', '.join(['?'] * len(tickers))
        query += f" WHERE ticker IN ({placeholders})"
        params = list(tickers)
        
    records = []
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        for row in cursor.fetchall():
            records.append({
                'ticker': row[0],
                'sectorname': row[1] or 'Unknown',
                'primaryname': row[2] or 'Unknown'
            })
            
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=['ticker', 'sectorname', 'primaryname'])
    return df
