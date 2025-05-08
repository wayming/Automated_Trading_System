
import os
import sys
import click
import pandas as pd
import yfinance as yf
from mock_executor import MockExecutor
from risk_management import RiskManager
from . import backtest
import matplotlib
import matplotlib.pyplot as plt
import bt
import json
import re
import time
from strategy_engine.live_trade import AlpacaExecutor
from news_scraper.scraper_trading_view import TradingViewScraper
from news_scraper.scraper_investing import InvestingScraper
from news_scraper.analyser_trading_view import TradingViewAnalyser
from news_scraper.analyser_investing import InvestingAnalyser

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

def execute_trade_for_event(trade_executor, scraper, analyser, risk_manager):
    news = scraper.fetch_news(limit=5)
    for n in news:
        try:
            print(f"\nAnalyse news {n}")
            analyse_result = analyser.analyse(n)
            if analyse_result is None:
                print("Skip the news without structure response.")
                continue
            else:
                print(f"Analysis result for {n}:")
                print(json.dumps(analyse_result, indent=2, ensure_ascii=False))
        except Exception as e:
            print("Error details:", e)
            continue

        # Check short term score if analysis exists
        if 'analysis' in analyse_result and 'short_term' in analyse_result['analysis']:
            try:
                ticker = analyse_result.get('stock_code', 'Unknown')

                # Extract numeric value from [+30] format
                score_str = analyse_result['analysis']['short_term']['score']
                score = int(re.search(r'[+-]?\d+', score_str).group())
                
                if score > 50:
                    print(f"\nPositive Signal for {analyse_result.get('stock_name', 'Unknown')} [{ticker}]")
                    print(f"Short Term Score: {score}")

                    price_data = yf.download(ticker, period="1d", interval="1m")
                    if price_data.empty or "Close" not in price_data.columns:
                        print(f"No data available for {ticker}, skipping.")
                        continue  # 或者 return，根据上下文跳出或终止

                    # 检查是否符合风险管理规则，决定是否买入
                    last_price = float(price_data["Close"].iloc[-1])  # 避免 FutureWarning
                    if risk_manager.check_position_limit(trade_executor.get_portfolio(), ticker, 100):
                        trade_executor.buy(ticker, last_price, 100)  # 买入100股
                        print(f"cash: {trade_executor.get_cash()}")
                        print("portfolio:")
                        print(json.dumps(trade_executor.get_portfolio(), indent=2))
                    else:
                        print(f"Not enough balance")
                        return

            except (ValueError, AttributeError, KeyError) as e:
                print("\nCould not parse score value")
                print("Error details:", e)
        else:
            print("\nNo short_term analysis available")
            
def mock_trade():
    # 模拟实盘交易的执行
    executor = MockExecutor(10000000)  # 初始100000现金
    risk_manager = RiskManager(0.1, 0.7)  # 每只股票最大持仓10%，止损70%

    TV_USERNAME = os.getenv("TRADE_VIEW_USER")
    TV_PASSWORD = os.getenv("TRADE_VIEW_PASS")
    DS_API_KEY = os.getenv("DEEPSEEK_API_KEY")

    news_sources = []

    in_scraper = InvestingScraper()
    if not in_scraper.login():
        return 
    news_sources.append((in_scraper, InvestingAnalyser(DS_API_KEY, "prompt.txt")))

    tv_scraper = TradingViewScraper(TV_USERNAME, TV_PASSWORD)
    if not tv_scraper.login():
        return
    news_sources.append((tv_scraper, TradingViewAnalyser(DS_API_KEY, "prompt.txt")))



    while True:
        for source in news_sources:
            execute_trade_for_event(executor, source[0], source[1], risk_manager)

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
