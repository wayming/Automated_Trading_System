import re
import json
from datetime import datetime
from typing   import Optional
from grpc     import RpcError 
class TradePolicy:
    def __init__(self, executor, logger):
        self.executor = executor
        self.logger = logger

    def evaluate(self, analyse_result: Optional[dict]):
        if not analyse_result:
            self.logger.info("No trade operation for empty analysis results")
            return

        if ("analysis" in analyse_result and
            analyse_result["analysis"] is not None and
            "short_term" in analyse_result["analysis"]):
            try:
                ticker = analyse_result.get("stock_code", "Unknown")
                if not ticker:
                    self.logger.info("No impacted stock")
                    return

                score_str = analyse_result["analysis"]["short_term"].get("score")
                if not score_str:
                    self.logger.error("Score is missing or invalid")
                    return

                score = int(re.search(r'[+-]?\d+', score_str).group())
                if score > 50:
                    self._execute_buy(ticker, score, analyse_result)
                else:
                    self.logger.info(f"Score is not a buy signal ({score})")

            except (ValueError, AttributeError, KeyError, TypeError) as e:
                self.logger.error("Could not parse score or ticker")
                self.logger.exception(e)
        else:
            self.logger.info("No short_term analysis available")
        self.logger.info("Evaluation done")

    def _execute_buy(self, ticker: str, score: int, analyse_result: dict):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[{timestamp}] Positive Signal for {analyse_result.get('stock_name', 'Unknown')} [{ticker}]")
        self.logger.info(f"Short Term Score: {score}")

        # Fixed quantity for now
        quantity = 10.0
        try:
            # Attempt to execute the trade
            self.executor.execute_trade(ticker, "buy", quantity)
        except RpcError as e:
            # Handle any gRPC error (including _InactiveRpcError)
            self.logger.error(f"Error during trade execution for {ticker}: {e.details()} - {e.debug_error_string}")

        # Log portfolio and cash after trade
        if hasattr(self.executor, "get_cash") and hasattr(self.executor, "get_portfolio"):
            self.logger.info(f"Cash: {self.executor.get_cash()}")
            self.logger.info("Portfolio:")
            self.logger.info(json.dumps(self.executor.get_portfolio(), indent=2))