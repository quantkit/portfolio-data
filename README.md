# portfolio-data

## Overview

This program takes CoinTracking.info trade data in CSV format and does the following:

- Matches buy and sell amounts from trades using first-in-first-out (FIFO) methodology.
- Creates realized and unrealized totals for each cryptocurrency, calculated in fiat and other cryptocurrencies (BTC and ETH by default).  The program uses CryptoCompare.com and CoinMarketCap.com APIs to retrieve historical and current prices, respectively.
- Creates realized and unrealized per unit totals for each cryptocurrency, calculated in fiat and other cryptocurrencies (BTC and ETH by default).
- Outputs Excel workbook with above data.

## Instructions

### CoinTracking.info Setup

Create an account if you don't already have one.

#### Import Trades

- Go to Account > Account Settings > Your time zone > Set to (UTC) Coordinated Universal Time > Save user settings.  This setting is necessary because CoinTracking.info does not store time zone information with trade dates.  Therefore, this program will interpret all trade dates as UTC time.  This setting must be made in CoinTracking.info before importing your trades.
Use one of the following three methods to import your trades:
  - API import (paid accounts only): Enter Coins > Exchange API Imports
  - Exchange file import (paid or free accounts): Enter Coins > Exchange Imports
  - CSV import (paid or free accounts): Enter Coins > Bulk Imports > CSV Import.  Upload any remaining trades (e.g., ICOs) that aren't covered under the first two methods.  Enter trade date values in UTC.  Buy and sell amounts must be inclusive of the fee amount.  See the Known Issues section for more details on accounting for fee amounts.

#### Export Trades

- Reporting > Trade List > Change to full view > Manage Columns > Select "Buy value in (fiat currency)" and "Sell value in (fiat currency)".
- Click CSV button to export file.

### Python Setup

This program requires Python 3 and has some dependencies.  If you are running Ubuntu, the following commands can be used to install the dependencies.  If you are running Windows 10, you can install Ubuntu here: https://www.microsoft.com/en-us/store/p/ubuntu/9nblggh4msv6
```
sudo apt-get update
sudo apt-get install python3-pip
python3 -m pip install pandas requests-cache xlsxwriter --user
```

Download the calc.py file from this repository.  Place the CoinTracking.info CSV file in the same directory as the Python file and run the following command:
```
python3 calc.py
```


## Known Issues

1.  The CoinTracking.info system expresses buy and sell amounts inclusive of fee amounts.  There are three possibilities:
    - The fee currency is the same as the buy currency.  In this case, CoinTracking.info will deduct the fee amount from the buy amount.
    - The fee currency is the same as the sell currency.  In this case, CoinTracking.info will add the fee amount to the sell amount.
    - The fee currency is different from the buy and sell currencies.  In this case, CoinTracking.info will do nothing with the fee amount.

    CoinTracking.info's design decision for fee amounts has two implications:
    - When creating a custom upload to CoinTracking.info (e.g., ICO purchases), you must be sure to include the fee amount in either the buy or sell amount as specified above, if possible.  Otherwise, the fee amount will not be accounted for in CoinTracking.info, or in this program.
    - For transactions where the fee currency is different from the buy and sell currencies, fees will not be accounted for in CoinTracking.info, or in this program.

2.  For each transaction, CoinTracking.info has a fiat/BTC valuation for both the buy and sell side.  For example, the buy side of a transaction may be valued at $100 USD, but the sell side may be valued at $102 USD.  These separate valuations seem to cause problems in their system when calculating gains and losses, and taxes.  To avoid these problems, this program follows the below rules for each transaction:
    - The value of both sides of a transaction is always equal.  This program selects either the buy value or the sell value to represent the value of both sides of the transaction.  Using the previous example, the value of both sides of the transaction would equal either $100 or $102.
    - If only one side of the transaction exists, then the value of that side will be selected.  For example, mining income only has a buy side.
    - If the value currency was used on either the buy or sell side, then the value of that side will be selected to represent both sides.  For example, if the value currency is USD, and you bought 1 BTC with $10000 USD, the program will assign a value of $10000 USD to both the buy and sell sides.  As another example if the value currency is ETH, and you bought 1 BTC with 10 ETH, the program will assign a value of 10 ETH to both the buy and sell sides.
    - If none of the above rules apply, the program will select the sell value by default.  This is an arbitrary decision, as the buy value could be selected instead, but using the sell value works for more common cases.  For example, with ICOs you are typically selling ETH, and buying a new thinly traded asset.  In this case, using the sell value will result in a more accurate valuation for both sides of the trade.  This default behavior will not cover all cases.  Ideally, the program would be able to select either the buy or sell based on a market volume metric to ensure the most accurate valuation for both sides of the trade, but this is not currently implemented.

3.  Because of the fee amount issue and buy/sell valuation issue above, this program may not include fees in the values for some trades when doing its calculations.  For example, if the buy amount includes the fee amount, but this program selects the sell value to represent the value of both sides, the value will not include the fee.
