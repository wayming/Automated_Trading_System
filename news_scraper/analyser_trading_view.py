import os
import json
import re
import time
import asyncio
import requests
import aio_pika
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
from common             import new_logger, new_mq_conn, new_aws_conn
from trade_policy       import TradePolicy
from openai             import OpenAI

import grpc.aio
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc

# Set up logging
QUEUE_TV_ARTICLES = "tv_articles"
logger = new_logger("output/analyser_trading_view.log")

class TradingViewAnalyser(NewsAnalyser):
    def __init__(self, api_key: str, prompt_path: str):
        self.api_key = api_key
        self.prompt_path = prompt_path
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.ds_client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    def _extract_article(self, html_text):
        soup = BeautifulSoup(html_text, 'html.parser')

        title = soup.find('h1', class_='title-KX2tCBZq')
        content = soup.find('div', class_='body-KX2tCBZq')

        return {
            "title": title.text.strip() if title else "No Title",
            "content": "\n".join(p.get_text(strip=True) for p in content.find_all('p')) if content else "No Content"
        }

    def _send_to_llm(self, prompt_text):
        response = self.ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": prompt_text},
            ],
            stream=False
        )
        return response.choices[0].message.content

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

async def handle_message(message: aio_pika.IncomingMessage, analyser, trade_policy, analysis_push_gateway):
    async with message.process(ignore_processed=True):
        try:
            logger.info("[Analyser_Trading_View] new message received.")
            body_text = message.body.decode()

            logger.info("[Analyser_Trading_View] analyse")
            result = analyser.analyse(body_text)
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            if analysis_push_gateway is not None:
                logger.info("[Analyser_Trading_View] push analyse results to AWS")
                response = await analysis_push_gateway.Push(pb2.PushRequest(
                    message=json.dumps(result, indent=2, ensure_ascii=False)))
                logger.info(response.status_code, response.response_text)

            logger.info("[Analyser_Trading_View] trade")
            trade_policy.evaluate(result)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await message.reject(requeue=False)

async def main():
    logger.info("[Analyser_Trading_View] Connecting to RabbitMQ")
    connection, queue = await new_mq_conn(QUEUE_TV_ARTICLES)

    logger.info("[Analyser_Trading_View] Connecting to AWS Gateway")
    analysis_push_gateway = None
    aws_gateway_endpoint = os.getenv("AWS_GATEWAY_ENDPOINT")
    if not aws_gateway_endpoint:
        logger.warning("[Analyser_Trading_View] No AWS Gateway endpoint configured. Analysis results will not be pushed.")
    else:
        logger.info(f"[Analyser_Trading_View] Connecting to AWS Gateway at {aws_gateway_endpoint}")
        try:
            analysis_push_gateway = await new_aws_conn(aws_gateway_endpoint)
        except Exception as e:
            logger.error(f"[Analyser_Trading_View] Failed to initialize gRPC client for AWS Gateway: {e}")
            analysis_push_gateway = None

    logger.info("[Analyser_Trading_View] Creating deepseek analyser")
    this_dir = Path(__file__).parent
    analyser = TradingViewAnalyser(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        prompt_path=this_dir / "prompt.txt", # Under the same directory
    )

    logger.info("[Analyser_Trading_View] Creating trade executor")
    executor = MockTradeExecutorProxy()
    trade_policy = TradePolicy(executor=executor, logger=logger)

    logger.info("Setting up queue consumer")
    await queue.consume(
        partial(handle_message,
                analyser=analyser,
                trade_policy=trade_policy,
                analysis_push_gateway=analysis_push_gateway))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info("Consumer started, waiting for messages")
    await stop_event.wait()

    logger.info("Shutting down")
    await connection.close()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())