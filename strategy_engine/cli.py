
import os
import sys
import click
import pandas as pd
import yfinance as yf
import indicators
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
@click.command()
@click.argument("action", type=click.Choice(['run_backtest', 'mock_trade', 'live_trade', 'show_trade'], case_sensitive=False))
def main(action):
    if action == "run_backtest":
        run_backtest()
    elif action == "mock_trade":
        mock_trade()
    elif action == "live_trade":
        live_trade()
    elif action == "show_trade":
        show_trade()

def run_backtest():
    print("Running backtest...")
    matplotlib.use('TkAgg')  # 强制使用 TkAgg 后端
    tickers = backtest.get_target_tickers()
    price_data = backtest.get_price_data(tickers)
    print(price_data)
    backtest_strategy = backtest.create_strategy(price_data)
    result = bt.run(backtest_strategy)
    print(result.display())
    result.plot()
    plt.show()
    pass

def mock_trade():
    # 模拟实盘交易的执行
    executor = MockExecutor(100000)  # 初始100000现金
    risk_manager = RiskManager(0.1, 0.7)  # 每只股票最大持仓10%，止损70%

    # Usage
    USERNAME = os.getenv("TRADE_VIEW_USER")
    PASSWORD = os.getenv("TRADE_VIEW_PASS")
    driver = scraper_trading_view.auto_login_tradingview(USERNAME, PASSWORD)
    if not driver:
        print('no driver')
        sys.exit(1)

    # Run the function in a loop with 3-second delay
    while True:
        news = scraper_trading_view.read_message(driver)
        for n in news:
            result = analyser.run_pipeline(n, "prompt.txt")
            print("DeepSeek Response:\n")
            print(json.dumps(result, indent=2, ensure_ascii=False))  # Pretty print JSON
            
            # Check short term score if analysis exists
            if 'analysis' in result and 'short_term' in result['analysis']:
                try:
                    ticker = result['stock_code']

                    # Extract numeric value from [+30] format
                    score_str = result['analysis']['short_term']['score']
                    score = int(re.search(r'[+-]?\d+', score_str).group())
                    
                    if score > 10:
                        print(f"\nPositive Signal for {result.get('stock_name', 'Unknown')}")
                        print(f"Short Term Score: {score}")

                        price_data = yf.download(ticker, period="1d", interval="1m")

                        # 检查是否符合风险管理规则，决定是否买入
                        if risk_manager.check_position_limit(executor.get_portfolio(), ticker, 100):
                            executor.buy(ticker, price_data[ticker][-1], 100)  # 买入100股

                except (ValueError, AttributeError, KeyError):
                    print("\nCould not parse score value")
            else:
                print("\nNo short_term analysis available")

        time.sleep(3)

    print("模拟交易结束。")

def live_trade():
    # 初始化模块
    executor = AlpacaExecutor()
    risk_manager = RiskManager(max_position_size=0.1, stop_loss_threshold=0.7)  # Rust风控
    
    # 交易逻辑
    tickers = ["AAPL", "GOOG", "MSFT"]
    portfolio = executor.get_portfolio()
    
    for ticker in tickers:
        current_price = executor.get_market_price(ticker)
        
        # Rust风控检查
        if risk_manager.check_position_limit(portfolio, ticker, 100):
            executor.buy(ticker, 100)
        
        # 止损检查
        if risk_manager.check_stop_loss(portfolio, ticker, current_price):
            executor.sell(ticker, 100)  # 假设固定卖出100股

def show_trade():
    executor = AlpacaExecutor()
    print(executor.get_open_orders())

if __name__ == "__main__":
    main()
