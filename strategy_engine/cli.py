
import click
import indicators
import pandas as pd
import yfinance as yf
from mock_executor import MockExecutor
from risk_management import RiskManager

@click.command()
@click.argument("action", type=click.Choice(['run_backtest', 'live_trade'], case_sensitive=False))
def main(action):
    if action == "run_backtest":
        run_backtest()
    elif action == "live_trade":
        live_trade()

def run_backtest():
    print("Running backtest...")
    # 使用之前的 backtest.py 脚本运行回测逻辑
    pass

def live_trade():
    # 模拟实盘交易的执行
    executor = MockExecutor(100000)  # 初始100000现金
    risk_manager = RiskManager(0.1, 0.7)  # 每只股票最大持仓10%，止损70%

    tickers = ["AAPL", "GOOG", "MSFT"]
    price_data = yf.download(tickers, start="2020-01-01", end="2024-01-01")["Adj Close"]

    for ticker in tickers:
        # 检查是否符合风险管理规则，决定是否买入
        if risk_manager.check_position_limit(executor.get_portfolio(), ticker, 100):
            executor.buy(ticker, price_data[ticker][-1], 100)  # 买入100股

    print("实盘交易模拟结束。")

if __name__ == "__main__":
    main()
