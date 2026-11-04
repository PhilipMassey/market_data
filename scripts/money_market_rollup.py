from click import globals
import os
import sys
import glob
from os.path import join
from datetime import datetime
import pandas as pd
# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
download_dir = os.environ.get('DOWNLOAD_DIR')

def fidelity_positions_filep():
    files = glob.glob(download_dir + '/Portfolio_Positions*.csv')
    if len(files) != 1:
        raise Exception("File size is not 1")
    fn = files[0]
    date_str = fn[-15:].rsplit('.', 1)[0]
    a_date = datetime.strptime(date_str, '%b-%d-%Y')
    return a_date, files[0]


def df_fidelity_positions_portfolio():
    a_date, filep = fidelity_positions_filep()
    fidelity_df = pd.read_csv(filep, header=0, index_col=False)
    fidelity_df = fidelity_df.dropna(how='all', subset=['Symbol'])
    fidelity_df['Symbol'] = fidelity_df['Symbol'].replace('Pending Activity', 'FDRXX**')
    return a_date, fidelity_df


def write_df_to_file(df, file_path):
    output_string = df.to_string(index=False)
    with open(file_path, 'w') as f:
        f.write(output_string)

def money_market():
    a_date, fidelity_df = df_fidelity_positions_portfolio()
    fidelity_df['Current value'] = fidelity_df['Current value'].str.replace('$', '').astype(float)
    filter_values = ['FDRXX',"CORE", 'SPAXX','Pending activity']
    fidelity_df = fidelity_df[fidelity_df['Symbol'].str.contains('|'.join(filter_values))]
    fidelity_df = fidelity_df[['Account name', 'Current value']]
    fidelity_df = fidelity_df.groupby('Account name').agg({'Current value': 'sum'})
    total_current_value = fidelity_df['Current value'].sum()
    new_row = {'Account name': 'Total', 'Current value': total_current_value}
    new_row_df = pd.DataFrame([new_row])
    fidelity_df.reset_index(inplace=True)
    fidelity_df = pd.concat([fidelity_df, new_row_df], ignore_index=True)
    filep = join(download_dir, 'Money Market.txt')
    write_df_to_file(fidelity_df, filep)
    print('Completed Filing Money Market: ', filep)

if __name__ == "__main__":
    money_market()
