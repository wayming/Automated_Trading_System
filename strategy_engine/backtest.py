
import bt
import pandas as pd
import indicators  # 引入 Rust 模块

# 获取 Rust 输出的股票推荐列表
def get_target_tickers():
    indicators.get_sma(['AAPL', 'MSFT', 'GOOG', 'AMZN'], 50)
    df = pd.read_csv("signals.csv")
    return df['ticker'].tolist()

# 获取历史股价数据
def get_price_data(tickers):
    import yfinance as yf
    data = yf.download(tickers, start="2020-01-01", end="2024-01-01", auto_adjust=False)["Adj Close"]
    return data.dropna(axis=1)

# 策略定义：每月调仓，按SMA选股
def create_strategy(price_data):
    """Create backtest strategy with monthly rebalancing"""
    if price_data.empty:
        raise ValueError("No price data available for selected tickers")
    
    # The working solution: Use WeighEqually instead of WeighTarget
    strategy = bt.Strategy("SMA_Momentum_Strategy", [
        bt.algos.RunMonthly(),
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),  # This handles equal weighting automatically
        bt.algos.Rebalance()
    ])
    
    return bt.Backtest(strategy, price_data)


if __name__ == "__main__":
    tickers = get_target_tickers()
    price_data = get_price_data(tickers)
    print(price_data)
    backtest = create_strategy(price_data)
    result = bt.run(backtest)
    result.plot()