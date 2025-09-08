from langchain_core.tools import tool

@tool
async def get_prices(stock_symbol: str) -> dict:
    """Get stock prices"""
    return {"stock_symbol": stock_symbol, "open": 0, "close": 0, "high": 0, "low": 0, "volume": 0}\

@tool
async def get_indicators(stock_symbol: str) -> dict:
    """Get indicators"""
    return {"stock_symbol": stock_symbol, "rsi": 50, "macd": 0, "volume_change": 0}
