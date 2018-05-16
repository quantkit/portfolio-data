import csv
from datetime import timezone
import numpy as np
import os
import pandas as pd
import pandas.io.formats.excel
import requests
from requests.adapters import HTTPAdapter
import requests_cache
from requests.packages.urllib3.util.retry import Retry
from statistics import mean
import time
import xlsxwriter

def retry_session(url, error_codes, expire_after=None):
  session = requests_cache.CachedSession(allowable_codes=(200,), expire_after=expire_after)
  retry = Retry(
      total=12,
      backoff_factor=0.1,
      method_whitelist=('GET', 'POST'),
      status_forcelist=error_codes
  )
  adapter = HTTPAdapter(max_retries=retry)
  session.mount(url, adapter)
  return session

def get_valuation_cryptocurrencies(cryptocompare_session):
  cryptocompare_currencies = get_cryptocompare_currencies(cryptocompare_session)
  user_input_valid = False
  
  while not user_input_valid:    
    user_input = input('Input the valuation cryptocurrencies you want to use, separated by commas (or leave blank to use the default of BTC, ETH), and press enter: ')
    
    if user_input.strip() == '':
      valuation_cryptocurrencies = ['BTC', 'ETH']
      user_input_valid = True
    else:
      valuation_cryptocurrencies = []
      user_input_currencies = [currency.upper().strip() for currency in user_input.split(',')]
      for currency in user_input_currencies:
        if not currency in valuation_cryptocurrencies:
          valuation_cryptocurrencies.append(currency)
      unsupported_currencies = list(set(valuation_cryptocurrencies).difference(cryptocompare_currencies))

      if unsupported_currencies:
        print('\n' + 'The following currencies are not supported by the CryptoCompare API: ' + ','.join(unsupported_currencies) + '.  Please try again with a different list of currencies.'+ '\n')
      else:
        user_input_valid = True
      
  return valuation_cryptocurrencies

def get_cryptocompare_currencies(cryptocompare_session):
  error_message = '\n' + 'The program encountered an error while trying to retrieve historical prices from the CryptoCompare API.  Please try running the program again later.'
  try:
    response = get_request(cryptocompare_session, cryptocompare_api_base_url + 'all/coinlist')    
    response_json = response.json()
    
    if response_json['Response'] == 'Success':
      cryptocompare_currencies = [currency.upper().strip() for currency in response_json['Data']]
    else:
      print_error_message_and_exit(error_message)
  except:
    print_error_message_and_exit(error_message)

  return cryptocompare_currencies

def read_input_file(input_filename):
  try:
    input_df = pd.read_csv(input_filename, na_filter=False)
  except:
    print_error_message_and_exit('The program encountered an error while trying to read the input file.  Please make sure there is a file named "' + input_filename + '" in the same directory as the program file named "' + os.path.basename(__file__) + '", and try running the program again.')
  return input_df

def print_error_message_and_exit(error_message):
  print(error_message)
  raise SystemExit

def format_columns(columns):
  new_columns = []
  previous_column = None
  
  for current_column in columns:
    current_column = current_column.lower().replace(' ', '_').strip()
    current_column = current_column.replace('_in_', '_')
    if current_column.startswith('cur.'):
      current_column = previous_column + '_currency'
    new_columns.append(current_column)
    previous_column = current_column   
    
  return new_columns

def get_primary_valuation_currency(columns):
  primary_valuation_currency = None
  
  for column in columns:
    if column.startswith('buy_value_'):
      currency = column.split('_')[-1].upper()
      if get_is_currency_fiat(currency):
        primary_valuation_currency = currency

  if not primary_valuation_currency:
    print_error_message_and_exit('The input file does not have a buy value column in a supported fiat currency.  Please provide an input file with a buy value column in one of the following fiat currencies and run the program again: ' + ', '.join(fiat_currencies) + '.')
  return primary_valuation_currency

def check_for_required_columns(columns):
  primary_valuation_currency = get_primary_valuation_currency(columns).lower()

  required_columns = ['type', 'buy', 'buy_currency', 'buy_value_' + primary_valuation_currency, 'sell', 'sell_currency', 'sell_value_' + primary_valuation_currency, 'exchange', 'comment', 'trade_date']

  missing_columns = list(set(required_columns).difference(columns))
  
  if missing_columns:
    print_error_message_and_exit('The input file is missing the following required column(s): ' + ', '.join(missing_columns) + '.  Please correct the input file and run the program again.')  

def format_values(input_df):
  primary_valuation_currency = get_primary_valuation_currency(input_df.columns).lower()
  
  input_df['type'] = input_df['type'].astype(str)
  input_df['buy'] = input_df['buy'].astype(str).replace('-', '0').astype(float)
  input_df['buy_currency'] = input_df['buy_currency'].astype(str)
  input_df['buy_value_' + primary_valuation_currency] = input_df['buy_value_' + primary_valuation_currency].astype(float)
  input_df['sell'] = input_df['sell'].astype(str).replace('-', '0').astype(float)
  input_df['sell_currency'] = input_df['sell_currency'].astype(str)
  input_df['sell_value_' + primary_valuation_currency] = input_df['sell_value_' + primary_valuation_currency].astype(float)
  input_df['exchange'] = input_df['exchange'].astype(str)
  input_df['comment'] = input_df['comment'].astype(str)
  input_df['trade_date'] = pd.to_datetime(input_df['trade_date'], format='%d.%m.%Y %H:%M')
  input_df = input_df.round(internal_decimal_places)
  input_df.fillna('', inplace=True)
  
  return input_df

def add_trade_valuations_to_input_df(input_df, valuation_currencies, cryptocompare_session):
  primary_valuation_currency = valuation_currencies[0].lower()
  
  for valuation_currency in valuation_currencies:
    valuation_currency = valuation_currency.lower()    

    for side in ['buy', 'sell']:
      primary_valuation_column = side + '_value_' + primary_valuation_currency
        
      if valuation_currency != primary_valuation_currency:
        valuation_column = side + '_value_' + valuation_currency
        input_df[valuation_column] = input_df.apply(lambda row : convert_historical_trade_valuation(row[primary_valuation_column], primary_valuation_currency, valuation_currency, row['trade_date'], cryptocompare_session), axis=1)

    input_df['buy_value_' + valuation_currency] = input_df.apply(lambda row : set_trade_valuation(row, valuation_currency), axis=1)
    
    input_df['sell_value_' + valuation_currency] = input_df['buy_value_' + valuation_currency]
  
  return input_df

def convert_historical_trade_valuation(from_value, from_currency, to_currency, trade_date, cryptocompare):
  return from_value * get_cryptocompare_average_hourly_price(from_currency, to_currency, trade_date, cryptocompare)
  
def get_cryptocompare_average_hourly_price(from_currency, to_currency, date, cryptocompare_session):
  unix_time = str(int(date.replace(tzinfo=timezone.utc).timestamp()))
  from_currency = from_currency.upper()
  to_currency = to_currency.upper()
  result = None
  
  try:
    response = get_request(cryptocompare_session, cryptocompare_api_base_url + 'histohour?fsym=' + from_currency + '&tsym=' + to_currency + '&limit=1&toTs=' + unix_time)
    response_json = response.json()

    if response_json['Response'] == 'Success':
      result = mean([price['close'] for price in response_json['Data']])
    else:
      print_error_message_and_exit('The program encountered an error while trying to convert ' + from_currency + ' to ' + to_currency + '.  It is likely that CryptoCompare does not have data for one of these currencies.  Please select a different currency conversion pair and try running the program again.')
  except:
    print_error_message_and_exit('The program encountered an error while trying to retrieve historical prices from the CryptoCompare API.  Please try running the program again later.')
  return result

def get_request(session, url):
  headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.40 Safari/537.36'
    }
  return session.get(url, headers=headers, timeout=5)
  
def set_trade_valuation(row, valuation_currency):
  buy = row['buy']
  sell = row['sell']
  
  if row['buy_currency'].upper() == valuation_currency:
    result = buy
  elif row['sell_currency'].upper() == valuation_currency:
    result = sell
  elif not sell or sell == 0:
    result = row['buy_value_' + valuation_currency]
  else:
    result = row['sell_value_' + valuation_currency]
  return result

def get_is_currency_fiat(currency):
  return currency.upper() in fiat_currencies
  
def create_buy_or_sell_df(input_df, side, valuation_currencies):
  valuation_columns = get_valuation_columns([side + '_value_'], valuation_currencies)

  primary_valuation_currency = get_primary_valuation_currency(input_df.columns).lower()
  df = input_df.loc[(input_df[side] != 0) & (input_df[side + '_is_currency_fiat'] == False), [side, side + '_currency'] + valuation_columns + ['exchange', 'comment', 'trade_date']]
  
  return df

def get_valuation_columns(prefixes, valuation_currencies):
  valuation_columns = [prefix + currency.lower() for currency in valuation_currencies for prefix in prefixes]
  
  return valuation_columns
  
def check_for_valid_buy_and_sell_quantities(buy_df, sell_df):
  for currency in sell_df['sell_currency'].unique():
    if sell_df.loc[sell_df['sell_currency'] == currency, 'sell'].sum().round(internal_decimal_places) > buy_df.loc[buy_df['buy_currency'] == currency, 'buy'].sum().round(internal_decimal_places):
      print_error_message_and_exit('The units sold of ' + currency + ' exceed the units acquired.  Please correct the input file and try again.')

def create_buy_and_sell_match_df(buy_df, sell_df, valuation_currencies):
  primary_valuation_currency = valuation_currencies[0].lower()
  
  valuation_columns = get_valuation_columns(['buy_value_', 'sell_value_'], valuation_currencies)
  
  buy_and_sell_match_df = pd.DataFrame(columns=['currency', 'quantity', 'buy_date', 'sell_date'] + valuation_columns + ['buy_exchange', 'sell_exchange', 'buy_comment', 'sell_comment'])

  while len(sell_df.index) > 0:
    sell_row_index = sell_df['trade_date'].idxmin()
    sell_row = sell_df.loc[sell_row_index]
    sell_currency = sell_row['sell_currency']
    buy_row_index = buy_df.loc[buy_df['buy_currency'] == sell_currency, 'trade_date'].idxmin()
    buy_row = buy_df.loc[buy_row_index]
    sell_date = sell_row['trade_date']
    buy_date = buy_row['trade_date']
    
    if sell_date < buy_date:
      print_error_message_and_exit('Sell for ' + sell_currency + ' on ' + str(sell_date) + ' cannot be matched with a buy.  The closest buy occurred at a later date: ' + str(buy_date) + '.  Please correct input file and try again.')
    
    buy_quantity = buy_row['buy']
    sell_quantity = sell_row['sell']
    match_quantity = min(buy_quantity, sell_quantity)
    
    match_dict = {}
    buy_valuation_columns = get_valuation_columns(['buy_value_'], valuation_currencies)
    sell_valuation_columns = get_valuation_columns(['sell_value_'], valuation_currencies)
    
    for column in buy_valuation_columns:
      match_dict[column] = calculate_trade_match_value(match_quantity, buy_quantity, buy_row[column])

    for column in sell_valuation_columns:
      match_dict[column] = calculate_trade_match_value(match_quantity, sell_quantity, sell_row[column])

    match_values = [match_dict[column] for column in valuation_columns]
    
    if sell_row['comment'].lower().strip() != 'gift':
      buy_and_sell_match_df.loc[len(buy_and_sell_match_df.index)] = [sell_currency, match_quantity, buy_date, sell_date] + match_values + [buy_row['exchange'], sell_row['exchange'], buy_row['comment'], sell_row['comment']]
  
    subtract_match(buy_df, buy_row_index, 'buy', match_quantity, match_dict)
    subtract_match(sell_df, sell_row_index, 'sell', match_quantity, match_dict)

  buy_and_sell_match_df = add_gain_loss_to_df(buy_and_sell_match_df, valuation_currencies)
  
  columns = buy_and_sell_match_df.columns
  
  buy_and_sell_match_df = pd.concat([buy_and_sell_match_df, buy_df.rename(columns={'buy':'quantity', 'buy_currency':'currency', 'exchange':'buy_exchange', 'comment':'buy_comment', 'trade_date':'buy_date'})], ignore_index=True)
  
  buy_and_sell_match_df = buy_and_sell_match_df[columns]

  buy_and_sell_match_df.sort_values(by=['sell_date', 'buy_date'], ascending=False, inplace=True)

  return buy_and_sell_match_df

def calculate_trade_match_value(match_quantity, trade_quantity, trade_valuation):
  return round((match_quantity / trade_quantity) * trade_valuation, internal_decimal_places)

def subtract_match(df, index, side, match_quantity, match_dict):
  df.loc[index, side] = round(df.loc[index, side] - match_quantity, internal_decimal_places)
  for valuation_column in match_dict:
    if valuation_column in df.columns:
      df.loc[index, valuation_column] = round(df.loc[index, valuation_column] - match_dict[valuation_column], internal_decimal_places)
  if df.loc[index, side] == 0:
    df.drop(index, inplace=True)

def add_gain_loss_to_df(df, valuation_currencies):
  for currency in valuation_currencies:
    currency = currency.lower()
    buy_value_column = 'buy_value_' + currency
    sell_value_column = 'sell_value_' + currency
    gain_loss_column = 'gain_loss_' + currency

    if gain_loss_column in df.columns:
      df.drop(gain_loss_column, axis=1, inplace=True)
    df.insert(df.columns.get_loc(sell_value_column) + 1, gain_loss_column, df[sell_value_column] - df[buy_value_column])
    
  return df

def create_realized_totals_df(buy_and_sell_match_df, pivot_values, margins_name):
  buy_and_sell_realized_df = buy_and_sell_match_df.copy()
  buy_and_sell_realized_df['sell_year'] = buy_and_sell_realized_df['sell_date'].dt.year
  buy_and_sell_realized_df = buy_and_sell_realized_df.loc[buy_and_sell_realized_df['sell_date'].notnull()]
  pivot_index = ['sell_year', 'currency']
  
  realized_totals_df = create_totals_df(buy_and_sell_realized_df, pivot_index, pivot_values, True, margins_name)
  
  return realized_totals_df
  
def create_totals_df(df, pivot_index, pivot_values, margins, margins_name):
  totals_df = pd.pivot_table(df, index=pivot_index, values=pivot_values, aggfunc=np.sum, margins=margins, margins_name=margins_name)

  totals_df.reset_index(inplace=True)
  totals_df = totals_df[pivot_index + pivot_values]
  first_column = totals_df.columns[0]
  totals_df.loc[totals_df[first_column] == margins_name, 'quantity'] = np.NaN
  
  return totals_df

def create_average_prices_df(totals_df, columns, margins_name):
  totals_df = totals_df.copy()
  
  for column in columns:
    totals_df[column] = totals_df[column] / totals_df['quantity']

  first_column = totals_df.columns[0]
  totals_df = totals_df[totals_df[first_column] != 'Total']
  
  return totals_df

def create_unrealized_totals_df(buy_and_sell_match_df, pivot_values, valuation_currencies, margins_name, coinmarketcap_session):
  unrealized_totals_df = create_totals_df(buy_and_sell_match_df.loc[buy_and_sell_match_df['sell_date'].isnull()], ['currency'], pivot_values, False, margins_name)

  coinmarketcap_id_dict = get_coinmarketcap_ids(coinmarketcap_session)
  
  for currency in valuation_currencies:
    currency = currency.lower()
    unrealized_totals_df['sell_value_' + currency] = unrealized_totals_df.apply(lambda row : row['quantity'] * get_coinmarketcap_current_price(row['currency'], currency, coinmarketcap_id_dict, coinmarketcap_session), axis=1)
  
  unrealized_totals_df = add_gain_loss_to_df(unrealized_totals_df, valuation_currencies)
  
  unrealized_totals_df = create_totals_df(unrealized_totals_df, ['currency'], pivot_values, True, margins_name)
  
  return unrealized_totals_df

def get_coinmarketcap_ids(coinmarketcap_session):
  try:
    with coinmarketcap_session.cache_disabled():
      response = get_request(coinmarketcap_session, coinmarketcap_api_base_url + 'listings/')

  except:
    print_error_message_and_exit('The program encountered an error while trying to retrieve coin IDs from the CoinMarketCap API.  Please try running the program again later.')

  coinmarketcap_id_dict = {}
    
  for coin in response.json()['data']:
    coinmarketcap_id_dict[coin['symbol'].upper()] = coin['id']
    
  coinmarketcap_id_dict['CPC'] = 2482

  return coinmarketcap_id_dict

def get_coinmarketcap_current_price(from_currency, to_currency, coinmarketcap_id_dict, coinmarketcap_session):
  coinmarketcap_id = coinmarketcap_id_dict.get(from_currency.upper())

  if coinmarketcap_id:
    to_currency = to_currency.upper()
    try:
      with requests_cache.disabled():
        response = get_request(coinmarketcap_session, coinmarketcap_api_base_url + 'ticker/' + str(coinmarketcap_id) +  '/?convert=' + to_currency)
    except Exception as e:
      print(e)
      print_error_message_and_exit('The program encountered an error while trying to retrieve current prices from the CoinMarketCap.com API.  Please try running the program again later.')
    current_price = float(response.json()['data']['quotes'][to_currency]['price'])
  else:
    print('\n' + 'CoinMarketCap does not have the current price for ' + from_currency + '.  The currency will have a current value of zero in the output file.')
    current_price = 0
  time.sleep(0.2)
  return current_price
  
def format_excel_sheet(df, sheet):
  max_width_list = [len(column) + 2 for column in df.columns]
  for i, width in enumerate(max_width_list):
    sheet.set_column(i, i, width)
  
  sheet.autofilter(0, 0, len(df.index) - 1, len(df.columns) - 1)
  sheet.freeze_panes(1, 0)

def write_excel_sheet(df, writer, sheet_name):
  df.to_excel(writer, sheet_name = sheet_name, index=False)
  format_excel_sheet(df, writer.sheets[sheet_name])
  
  return writer

def output_excel_file(writer, excel_output_filename):
  try:
    writer.save()
  except:
    print_error_message_and_exit('\n' + 'The program encountered an error while trying to write the Excel output file named "' + excel_output_filename + '".  Please ensure this file is closed and try running the program again.')

def main():
  cryptocompare_session = retry_session(cryptocompare_api_base_url, error_codes, expire_after=None)
  coinmarketcap_session = retry_session(coinmarketcap_api_base_url, error_codes, expire_after=120)
  
  input_df = read_input_file(cointracking_input_filename)
  original_input_df = input_df.copy()
  input_df.columns = format_columns(input_df.columns)
  
  primary_valuation_currency = get_primary_valuation_currency(input_df.columns)

  valuation_currencies = [primary_valuation_currency] + get_valuation_cryptocurrencies(cryptocompare_session)
  
  check_for_required_columns(input_df.columns)
  
  input_df = format_values(input_df)

  input_df['buy_is_currency_fiat'] = input_df['buy_currency'].apply(lambda x : get_is_currency_fiat(x))
  
  input_df['sell_is_currency_fiat'] = input_df['sell_currency'].apply(lambda x : get_is_currency_fiat(x))
  
  add_trade_valuations_to_input_df(input_df, valuation_currencies, cryptocompare_session)
  
  buy_df = create_buy_or_sell_df(input_df, 'buy', valuation_currencies)
  sell_df = create_buy_or_sell_df(input_df, 'sell', valuation_currencies)
  
  check_for_valid_buy_and_sell_quantities(buy_df, sell_df)
  
  buy_and_sell_match_df = create_buy_and_sell_match_df(buy_df, sell_df, valuation_currencies)
  
  valuation_columns = get_valuation_columns(['buy_value_', 'sell_value_', 'gain_loss_'], valuation_currencies)
  pivot_values = ['quantity'] + valuation_columns
  margins_name = 'Total'
  
  realized_totals_df = create_realized_totals_df(buy_and_sell_match_df, pivot_values, margins_name)
  realized_average_prices_df = create_average_prices_df(realized_totals_df, valuation_columns, margins_name)

  valuation_columns = get_valuation_columns(['buy_value_', 'sell_value_', 'gain_loss_'], valuation_currencies)
  
  unrealized_totals_df = create_unrealized_totals_df(buy_and_sell_match_df, pivot_values, valuation_currencies, margins_name, coinmarketcap_session)
  unrealized_average_prices_df = create_average_prices_df(unrealized_totals_df, valuation_columns, margins_name)
  
  buy_and_sell_match_df = buy_and_sell_match_df.round(8)
  buy_and_sell_match_df['buy_date'] = buy_and_sell_match_df['buy_date'].dt.strftime('%Y-%m-%dT%H:%M:%S+00:00').replace('NaT', '')
  buy_and_sell_match_df['sell_date'] = buy_and_sell_match_df['sell_date'].dt.strftime('%Y-%m-%dT%H:%M:%S+00:00').replace('NaT', '')
  realized_totals_df = realized_totals_df.round(2)
  realized_average_prices_df = realized_average_prices_df.round(8)
  unrealized_totals_df = unrealized_totals_df.round(2)
  unrealized_average_prices_df = unrealized_average_prices_df.round(8)
  
  writer = pd.ExcelWriter(excel_output_filename, engine='xlsxwriter')
  write_excel_sheet(original_input_df, writer, 'input')
  write_excel_sheet(buy_and_sell_match_df, writer, 'buy_and_sell_match')
  write_excel_sheet(realized_totals_df, writer, 'realized_totals')
  write_excel_sheet(realized_average_prices_df, writer, 'realized_average_prices')
  write_excel_sheet(unrealized_totals_df, writer, 'unrealized_totals')
  write_excel_sheet(unrealized_average_prices_df, writer, 'unrealized_average_prices')
  
  output_excel_file(writer, excel_output_filename)

  print('\n' + 'Successfully generated ' + excel_output_filename)
  
fiat_currencies = ['AED', 'ARS', 'AUD', 'BRL', 'CAD', 'CHF', 'CLP', 'CNY', 'CZK', 'DKK', 'EUR', 'GBP', 'HKD', 'HUF', 'IDR', 'ILS', 'INR', 'JPY', 'KRW', 'MXN', 'MYR', 'NOK', 'NZD', 'PHP', 'PKR', 'PLN', 'RON', 'RUB', 'SEK', 'SGD', 'THB', 'TRY', 'TWD', 'UAH', 'USD', 'ZAR']
  
internal_decimal_places = 8

pandas.io.formats.excel.header_style = None
pd.options.mode.chained_assignment = None

cointracking_input_filename = 'CoinTracking · Trade List.csv'
excel_output_filename = 'portfolio_data.xlsx'

error_codes = set([400, 401, 403, 404, 429, 500, 502, 503, 504])
cryptocompare_api_base_url = 'https://min-api.cryptocompare.com/data/'
coinmarketcap_api_base_url = 'https://api.coinmarketcap.com/v2/'

if __name__ == '__main__':
  main()
