import os
import json
import re
import time

import requests
import pika
import logging
import signal

from bs4                import BeautifulSoup
from requests.adapters  import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib            import Path
from .interface         import NewsAnalyser
from datetime           import datetime
from .executor_proxy    import TradeExecutor, MockTradeExecutorProxy

out_dir = 'output' # Mount volume

# Set up logging
log_file = os.path.join(out_dir, 'analyser_trading_view.log')
logging.basicConfig(
    filename=log_file,
    filemode='a',  # Append mode
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

QUEUE_TV_ARTICLES = "tv_articles"
class TradingViewAnalyser(NewsAnalyser):
    def __init__(self, api_key: str, prompt_path: str):
        self.api_key = api_key
        self.prompt_path = prompt_path
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _extract_article(self, html_text):
        soup = BeautifulSoup(html_text, 'html.parser')

        title = soup.find('h1', class_='title-KX2tCBZq')
        content = soup.find('div', class_='body-KX2tCBZq')

        return {
            "title": title.text.strip() if title else "No Title",
            "content": "\n".join(p.get_text(strip=True) for p in content.find_all('p')) if content else "No Content"
        }

    def _send_to_llm(self, prompt_text):
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.7
        }

        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))

        resp = session.post(self.api_url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']

    def _extract_structured_response(self, response_text):
        pattern = r'^-{3,}\s*\n(.*?)\n-{3,}$'
        match = re.search(pattern, response_text, re.DOTALL | re.MULTILINE)
        if not match:
            logger.info(f"No structure resposne found from llm response:\n{response_text}")
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON struct.\n{match.group(1)}\nError: {e}")
            return None

    def analyse(self, html_path: str) -> dict:

        article = self._extract_article(html_path)
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read()

        prompt = f"{base_prompt}\n\n---\n\nTitle: {article['title']}\n\nContent:\n{article['content']}"
        response = self._send_to_llm(prompt)

        result = self._extract_structured_response(response)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("\n\n" + ">"*80 + "\n")
        logger.info(f"Timestamp: {timestamp}\n")
        logger.info("Full Response:\n")
        logger.info(response)
        logger.info("\n" + ">"*80 + "\n\n")

        return result

def trade_on_score(analyse_result: str, executor: TradeExecutor):
    if analyse_result is None:
        logger.info("No trade operation for empty analysis results")
        return
    
    # Check short term score if analysis exists
    if 'analysis' in analyse_result and 'short_term' in analyse_result['analysis']:
        try:
            ticker = analyse_result.get('stock_code', 'Unknown')
            if ticker is None:
                logger.info("No impacted stock")
                return

            # Extract numeric value from [+30] format
            score_str = analyse_result['analysis']['short_term']['score']
            if score_str is None:
                logger.error("Not a valid score format")
                return
            score = int(re.search(r'[+-]?\d+', score_str).group())
            
            if score > 0:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Positive Signal for {analyse_result.get('stock_name', 'Unknown')} [{ticker}]")
                logger.info(f"Short Term Score: {score}")
                executor.execute_trade(ticker, "buy", 10.0)
                # price_data = yf.download(ticker, period="1d", interval="1m")
                # if price_data.empty or "Close" not in price_data.columns:
                #     print(f"No data available for {ticker}, skipping.")
                #     return  # 或者 return，根据上下文跳出或终止

                # # 检查是否符合风险管理规则，决定是否买入
                # last_price = float(price_data["Close"].iloc[-1])  # 避免 FutureWarning
                # if risk_manager.check_position_limit(trade_executor.get_portfolio(), ticker, 100):
                #     trade_executor.buy(ticker, last_price, 100)  # 买入100股
                #     print(f"cash: {trade_executor.get_cash()}")
                #     print("portfolio:")
                #     print(json.dumps(trade_executor.get_portfolio(), indent=2))
                # else:
                #     print(f"Not enough balance")
                #     return

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("\nCould not parse score value")
            logger.error("Error details:", e)
    else:
        logger.info("\nNo short_term analysis available")

def main():
    logger.info("[Analyser_Trading_View] Connecting to RabbitMQ...")
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='rabbitmq',
        heartbeat=600
    ))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_TV_ARTICLES)

    executor = MockTradeExecutorProxy()
    this_dir = Path(__file__).parent
    analyser = TradingViewAnalyser(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        prompt_path=this_dir/"prompt.txt",
    )

    logger.info("[Analyser_Trading_View] Waiting for messages...")
    while True:
        method_frame, properties, body = channel.basic_get(QUEUE_TV_ARTICLES, auto_ack=True)
        if method_frame:
            result = analyser.analyse(body.decode())
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            trade_on_score(result, executor)
        else:
            time.sleep(1)  # No message, wait briefly
        connection.process_data_events()  # Maintain heartbeat


if __name__ == "__main__":
    main()