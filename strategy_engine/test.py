
import os
import sys
import click
import pandas as pd
import yfinance as yf
from mock_executor import MockExecutor
from risk_management import RiskManager
import backtest
import matplotlib
import matplotlib.pyplot as plt
import bt
import json
import re
import time
from live_trade import AlpacaExecutor
from news_scraper import scraper_trading_view
from news_scraper import analyser

# 模拟实盘交易的执行
executor = MockExecutor(100000)  # 初始100000现金
risk_manager = RiskManager(0.1, 0.7)  # 每只股票最大持仓10%，止损70%

ticker='FNMA'
price_data = yf.download(ticker, period="1d", interval="1m")
print(price_data)
# 检查是否符合风险管理规则，决定是否买入
if risk_manager.check_position_limit(executor.get_portfolio(), ticker, 100):
    executor.buy(ticker, price_data["Close"].iloc[-1] , 100)  # 买入100股