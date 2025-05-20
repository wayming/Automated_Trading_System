from abc import ABC, abstractmethod
from typing import Dict, Tuple
import grpc
import os
import sys

from proto.trade_executor_pb2_grpc import TradeExecutorStub
from proto.trade_executor_pb2 import TradeRequest

class TradeExecutor(ABC):
    @abstractmethod
    def execute_trade(self, symbol: str, trade: str, amount: float) -> Tuple[str, float, Dict[str, float]]:
        pass


class MockTradeExecutorProxy(TradeExecutor):
    """
    Proxies trade execution requests to a remote gRPC mock trade executor service.
    """

    def __init__(self, host: str = "mock_executor", port: int = 50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = TradeExecutorStub(self.channel)

    def execute_trade(self, symbol: str, trade: str, amount: float) -> Tuple[str, float, Dict[str, float]]:
        request = TradeRequest(symbol=symbol, trade=trade, amount=amount)
        response = self.stub.ExecuteTrade(request)
        return response.message, response.cash_balance, dict(response.portfolio)
