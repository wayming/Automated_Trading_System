import os
import json
import re
import time

import requests
import pika
import logging
import signal
from functools          import partial
from bs4                import BeautifulSoup
from requests.adapters  import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib            import Path
from .interface         import NewsAnalyser
from datetime           import datetime
from .executor_proxy    import TradeExecutor, MockTradeExecutorProxy
from common             import new_logger, new_mq_conn
from trade_policy       import TradePolicy

# Set up logging
QUEUE_TV_ARTICLES = "tv_articles"
OUT_DIR = "output"
LOG_FILE = os.path.join(OUT_DIR, "analyser_trading_view.log")
logger = new_logger(LOG_FILE)

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

def main():
    logger.info("[Analyser_Trading_View] Connecting to RabbitMQ...")
    connection, channel = new_mq_conn(QUEUE_TV_ARTICLES)
    
    this_dir = Path(__file__).parent
    analyser = TradingViewAnalyser(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        prompt_path=this_dir/"prompt.txt",
    )
    
    executor = MockTradeExecutorProxy()
    trade_policy = TradePolicy(executor=executor, logger=logger)

    def on_message(ch, method, properties, body, analyser, trade_policy):
        logger.info("[Analyser_Trading_View] new message received.")
        result = analyser.analyse(body.decode())
        logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        trade_policy.evaluate(result)
        logger.info("[Analyser_Trading_View] acknowledge begin")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("[Analyser_Trading_View] acknowledge done")

    # Register signal handlers to stop consuming
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}. Stopping consumption.")
        channel.stop_consuming()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("[Analyser_Trading_View] Waiting for messages...")
    channel.basic_consume(
        queue=QUEUE_TV_ARTICLES,
        on_message_callback=partial(on_message, analyser=analyser, trade_policy=trade_policy)
    )

    try:
        channel.start_consuming()
    except Exception as e:
        logger.exception("Error during consuming")
    finally:
        logger.info("Closing connection...")
        channel.close()
        connection.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()