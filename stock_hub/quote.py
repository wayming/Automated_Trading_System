import os
import logging
import grpc
import yfinance as yf
from concurrent import futures
from proto import stock_hub_pb2, stock_hub_pb2_grpc
from datetime import datetime

# Ensure log directory exists
LOG_DIR = "output"
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logger
LOG_FILE = os.path.join(LOG_DIR, "quote_service.log")
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class QuoteService(stock_hub_pb2_grpc.StockQuoteServicer):
    def GetQuote(self, request, context):
        symbol = request.symbol.upper()
        logger.info(f"Received request for: {symbol}")

        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")

        if data.empty:
            logger.warning(f"No data for symbol: {symbol}")
            context.abort(404, f"No data found for {symbol}")

        latest = data.iloc[-1]
        price = float(latest["Close"])
        time_str = latest.name.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Quote for {symbol}: {price} at {time_str}")

        return stock_hub_pb2.QuoteResponse(
            symbol=symbol,
            price=price,
            currency=ticker.info.get("currency", "USD"),
            time=time_str
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    stock_hub_pb2_grpc.add_StockQuoteServicer_to_server(QuoteService(), server)
    server.add_insecure_port('[::]:50052')
    logger.info("📈 Quote service started on port 50052")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
