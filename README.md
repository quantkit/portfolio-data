# portfoliodata

## Overview

The program takes CoinTracking.info trade data in CSV format and does the following:

- Matches buys and sells of each cryptocurrency using first-in-first-out (FIFO) methodology.
- Calculates realized and unrealized totals for each cryptocurrency, valued in fiat and other cryptocurrencies (BTC and ETH by default).
- Calculates realized and unrealized average prices for each cryptocurrency, valued in fiat and other cryptocurrencies (BTC and ETH by default).
- Outputs Excel workbook with above data.

## Instructions

### CoinTracking.info Setup

Create an account if you don't already have one.

#### Import Trades to CoinTracking.info

- Go to Account > Account Settings > Your time zone > Set to (UTC) Coordinated Universal Time > Save user settings.  This setting is necessary because CoinTracking.info does not store time zone information with trade dates.  Therefore, the program will interpret all trade dates as UTC time.  Before importing your trades in CoinTracking.info, you must make this setting in order for the trade dates to be accurate.
Use one of the following three methods to import your trades:
  - API import (paid accounts only): Enter Coins > Exchange API Imports
  - Exchange file import (paid or free accounts): Enter Coins > Exchange Imports
  - CSV import (paid or free accounts): Enter Coins > Bulk Imports > CSV Import.  Upload any remaining trades (e.g., ICOs) that aren't covered under the first two methods.  Enter trade date values in UTC.  Buy and sell amounts must be inclusive of the fee amount.  See the Known Issues section for more details on accounting for fee amounts.
  - Import the following types of transactions:
    - Income (mining, airdrops, forks, gifts received)
    - Trades
    - Expenditures (purchases, gifts given).  All gifts given should have "Gift" in the comment field with no other text.
  - Do not import the following types of transactions:
    - Deposits and withdrawals of crypto between wallets, exchanges, etc.
  - The following types of transactions may be imported, but the program will ignore them:
    - Deposits and withdrawals of fiat

#### Export Trades from CoinTracking.info

- Reporting > Trade List > Change to full view > Manage Columns > Select "Buy value in (fiat currency)" and "Sell value in (fiat currency)".
- Click CSV button to export file.

### Python Setup

The program requires Python 3 and has some dependencies.  If you are running Ubuntu, the following commands can be used to install the dependencies.  If you are running Windows 10, you can install Ubuntu here: https://www.microsoft.com/en-us/store/p/ubuntu/9nblggh4msv6
```
sudo apt-get update
sudo apt-get install python3-pip
python3 -m pip install pandas requests-cache xlsxwriter --user
```
Download the portfoliodata.py file from this repository and place it in a writeable directory.  Place the CoinTracking.info CSV file in the same directory as the Python file and run the following command:
```
python3 portfoliodata.py
```
When prompted, input the valuation cryptocurrencies you want to use, separated by commas.  If nothing is entered, the program will use BTC and ETH as valuation cryptocurrencies by default.

## Implementation Details

1.  Fiat Currencies
    - The program uses the "Buy value in (fiat currency)" and "Sell value in (fiat currency)" columns from CoinTracking.info as the basis for all trade valuations.
    - The program supports the following fiat currencies:
      - AED, ARS, AUD, BRL, CAD, CHF, CLP, CNY, CZK, DKK, EUR, GBP, HKD, HUF, IDR, ILS, INR, JPY, KRW, MXN, MYR, NOK, NZD, PHP, PKR, PLN, RON, RUB, SEK, SGD, THB, TRY, TWD, UAH, USD, ZAR

2.  Currency Conversion
    - To convert valuations in fiat to valuations in cryptocurrencies, such as BTC and ETH, the program uses the CryptoCompare.com API.  The API makes available hourly historical prices.  The API returns prices for the two hours closest to each trade date.  The program averages these two prices when converting fiat to other valuation currencies.  The program uses an HTTP requests cache when calling this API.  So using a valuation cryptocurrency will take a long time on the first run, but will be significantly faster on subsequent runs.
    - The program uses the CoinMarketCap.com API to retrieve the most recent prices of current holdings.

3.  Trade Valuations
    - For each trade, CoinTracking.info has two fiat valuations: "Buy value in (fiat currency)" and "Sell value in (fiat currency)".  For example, the buy side of a trade may be valued at $100 USD, but the sell side may be valued at $102 USD.  The program follows the below rules when calculating trade valuations:
      - The value of both sides of a trade is always equal.  The program selects either the buy value or the sell value to represent the value of both sides of the trade.  Using the previous example, the value of both sides of the trade would be either $100 or $102.
      - If only one side of the trade exists, then the value of that side will be selected.  For example, mining income only has a buy side.
      - If the valuation currency was used on either the buy or sell side, then the value of that side will be selected to represent both sides.  For example, if the valuation currency is USD, and you bought 1 BTC with $10000 USD, the program will assign a value of $10000 USD to both the buy and sell sides.  As another example if the valuation currency is ETH, and you bought 1 BTC with 10 ETH, the program will assign a value of 10 ETH to both the buy and sell sides.
      - Unless a previous rule applies otherwise, the program will select the sell value by default.

4.  Income Treatment
    - The program treats all crypto deposits as income.  This is equivalent to buying the crypto on the trade date, for purposes of matching buys and sells of each cryptocurrency.
    
5.  Purchases / Gifts Given Treatment
    - The program treats all crypto withdrawals as purchases of good and services.  This is equivalent to selling the crypto on the trade date, for purposes of matching buys and sells of each cryptocurrency, and calculating realized gains/losses.  The one exception is if a crypto withdrawal has a comment field equal to "Gift".  In this case, this is still equivalent to selling the crypto on the trade date, for purposes of matching buys and sells of each cryptocurrency, but the trade is not included in the calculation of realized gains/losses.

## Known Issues

1.  The CoinTracking.info system expresses buy and sell amounts inclusive of fee amounts.  There are three possibilities:
    - The fee currency is the same as the buy currency.  In this case, CoinTracking.info will deduct the fee amount from the buy amount.
    - The fee currency is the same as the sell currency.  In this case, CoinTracking.info will add the fee amount to the sell amount.
    - The fee currency is different from the buy and sell currencies.  In this case, CoinTracking.info will do nothing with the fee amount.

    CoinTracking.info's design decision for fee amounts has two implications:
    - When creating a custom upload to CoinTracking.info (e.g., ICO purchases), you must be sure to include the fee amount in either the buy or sell amount as specified above, if possible.  Otherwise, the fee amount will not be accounted for in CoinTracking.info, or in the program.
    - For transactions where the fee currency is different from the buy and sell currencies, fees will not be accounted for in CoinTracking.info, or in the program.    

2.  As noted in Implementation Details under the Trade Valuations section, the program uses the sell value as the default valuation for both the buy and sell sides of the trade.  Using the sell value as default works for most common cases, but not all.  For example, with ICOs you are typically selling ETH, and buying a new thinly traded asset.  In this case, using the sell value will result in a more accurate valuation for both sides of the trade.  But, if you quickly sold ICO tokens after you acquired them, the buy value of the trade would be more accurate than the sell value.  Ideally, the program would be able to select either the buy or sell value based on a market volume metric for each currency to ensure the most accurate valuation for both sides of the trade, but this is not currently implemented.

3.  Because of the fee amount issue and buy/sell valuation issue above, the program may not include fees in the values for some trades when doing its calculations.  For example, if the buy amount includes the fee amount, but the program selects the sell value to represent the value of both sides, the value will not include the fee.
