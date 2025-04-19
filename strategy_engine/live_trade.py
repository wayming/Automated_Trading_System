
import alpaca_trade_api as tradeapi
import os

class AlpacaExecutor:
    def __init__(self):
        # 使用环境变量存储API密钥
        self.api_key = os.getenv('APCA_API_KEY_ID')  # 你的API Key
        self.api_secret = os.getenv('APCA_API_SECRET_KEY')  # 你的API Secret
        self.base_url = "https://paper-api.alpaca.markets"  # 使用 Alpaca 纸盘（模拟账户）环境
        self.api = tradeapi.REST(self.api_key, self.api_secret, self.base_url, api_version='v2')

    # 获取账户余额
    def get_balance(self):
        account = self.api.get_account()
        return float(account.cash)

    # 获取持仓
    def get_portfolio(self):
        positions = self.api.list_positions()
        portfolio = {}
        for position in positions:
            portfolio[position.symbol] = {
                'qty': position.qty,
                'avg_entry_price': position.avg_entry_price
            }
        return portfolio

    # 买入股票
    def buy(self, ticker: str, quantity: int, limit_price: float = None):
        try:
            if limit_price:
                self.api.submit_order(
                    symbol=ticker,
                    qty=quantity,
                    side='buy',
                    type='limit',
                    time_in_force='gtc',
                    limit_price=limit_price
                )
            else:
                self.api.submit_order(
                    symbol=ticker,
                    qty=quantity,
                    side='buy',
                    type='market',
                    time_in_force='gtc'
                )
            print(f"已下单买入 {ticker}，数量 {quantity}")
        except Exception as e:
            print(f"买入失败: {e}")

    # 卖出股票
    def sell(self, ticker: str, quantity: int, limit_price: float = None):
        try:
            if limit_price:
                self.api.submit_order(
                    symbol=ticker,
                    qty=quantity,
                    side='sell',
                    type='limit',
                    time_in_force='gtc',
                    limit_price=limit_price
                )
            else:
                self.api.submit_order(
                    symbol=ticker,
                    qty=quantity,
                    side='sell',
                    type='market',
                    time_in_force='gtc'
                )
            print(f"已下单卖出 {ticker}，数量 {quantity}")
        except Exception as e:
            print(f"卖出失败: {e}")

    # 获取股票当前市场价格
    def get_market_price(self, ticker: str):
        quote = self.api.get_latest_trade(ticker)
        return quote.price

    # 获取当前订单
    def get_open_orders(self):
        orders = self.api.list_orders(status='open')
        return orders