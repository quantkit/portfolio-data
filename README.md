# portfolio-data

## Overview

This program takes CoinTracking.info CSV output and does the following:

- Matches buy and sell amounts from trades for each cryptocurrency using first-in-first-out (FIFO) methodology.
- Creates realized and unrealized totals for each cryptocurrency, calculated in fiat and other cryptocurrencies (BTC and ETH by default).
- Creates realized and unrealized per unit totals for each cryptocurrency, calculated in fiat and other cryptocurrencies (BTC and ETH by default).
- Outputs Excel workbook with above data.

## Instructions

### CoinTracking.info Setup

- Create a free account.
- Go to Account > Account Settings > Your time zone > Set to (UTC) Coordinated Universal Time > Save user settings.
- Go to Enter Coins > Exchange Imports and upload trade files for any exchanges on the list.
- Go to Enter Coins > Bulk Imports > CSV Import and upload any remaining trades (e.g., ICOs).  Enter datetime values in UTC.  Buy and sell values must be inclusive of the fee value.
- Go to Reporting > Trade List > Change to full view > Manage Columns > Select "Buy value in (fiat currency)" and "Sell value in (fiat currency)".
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
