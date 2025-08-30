import os
import json
import re
import time
import asyncio
import requests
import aio_pika
import logging
import signal
from typing import Optional, Tuple
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
from dataclasses        import asdict
from datetime           import datetime, timezone

import grpc.aio
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc
import uuid

from news_model.processed_article import ProcessedArticle

# This module is responsible for analyzing trading view articles using DeepSeek's LLM.

# source
QUEUE_TV_ARTICLES = "tv_articles"

# destination
QUEUE_PROCESSED_ARTICLES = "processed_articles"

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
            logger.info(f"No structured resposne found from llm response:\n{response_text}")
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON struct.\n{match.group(1)}\nError: {e}")
            return None

    def analyse(self, html_text: str) -> Tuple[str, Optional[dict], str]:
        article = self._extract_article(html_text)
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read()

        prompt = f"{base_prompt}\n\n---\n\nTitle: {article['title']}\n\nContent:\n{article['content']}"
        response = self._send_to_llm(prompt)

        structured_result = self._extract_structured_response(response)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("\n\n" + ">"*80 + "\n")
        logger.info(f"Timestamp: {timestamp}\n")
        logger.info("Full Response:\n")
        logger.info(response)
        logger.info("\n" + ">"*80 + "\n\n")

        return article, structured_result, response.strip()
    
async def push_to_queue(queue: aio_pika.Queue, message: str):
    try:
        await queue.channel.default_exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=queue.name
        )
        logger.info(f"Message pushed to queue {queue.name}: {message[:80]}...")
    except Exception as e:
        logger.error(f"Failed to push message to queue {queue.name}: {e}")

async def handle_message(
        message: aio_pika.IncomingMessage,
        analyser, trade_policy, analysis_push_gateway,
        queue_processed_articles):
    async with message.process(ignore_processed=True):
        message_id=None
        try:
            message_id = str(uuid.uuid4())[:8]
            logger.info(f"[Analyser_Trading_View][{message_id}] New message received.")
            body_text = message.body.decode()

            logger.info(f"[Analyser_Trading_View][{message_id}] Analyzing message content...")
            article, struct_result, raw_text = analyser.analyse(body_text)

            analysis_message=None
            if struct_result is not None:
                analysis_message = json.dumps(struct_result, indent=2, ensure_ascii=False)
                logger.info(f"[Analyser_Trading_View][{message_id}] Structured analysis result:\n%s", analysis_message)
                logger.info(f"[Analyser_Trading_View][{message_id}] Evaluating trade policy")
                trade_policy.evaluate(struct_result)
            else:
                analysis_message = raw_text
                logger.info(f"[Analyser_Trading_View][{message_id}] No structured result, using raw text.")

            if analysis_push_gateway is not None:
                start = time.time()
                logger.info(f"[Analyser_Trading_View][{message_id}] Pushing analysis results to AWS at {time.ctime(start)}")
                try:
                    response = await asyncio.wait_for(
                        analysis_push_gateway.Push(pb2.PushRequest(message=analysis_message)),
                        timeout=600  # seconds
                    )
# async def fire_and_forget_push(analysis_push_gateway, message, message_id):
#     try:
#         await analysis_push_gateway.Push(pb2.PushRequest(message=message))
#         logger.info(f"[Analyser_Trading_View][{message_id}] Push fired (response ignored).")
#     except Exception as e:
#         logger.error(f"[Analyser_Trading_View][{message_id}] Fire-and-forget Push failed: {e}")

# # In your handler:
# asyncio.create_task(fire_and_forget_push(analysis_push_gateway, analysis_message, message_id))

                    logger.info(f"[Analyser_Trading_View][{message_id}] PushResponse: status_code=%d, response_text=%s",
                                response.status_code, response.response_text)
                except asyncio.TimeoutError:
                    logger.error(f"[Analyser_Trading_View][{message_id}] Push request timed out after {time.time() - start:.2f} seconds, skipping or retrying")
                except Exception as grpc_err:
                    logger.error(f"[Analyser_Trading_View][{message_id}] Failed to push to AWS: {grpc_err}")

            if struct_result is not None:
                logger.info(f"[Analyser_Trading_View][{message_id}] Pushing processed article to queue {QUEUE_PROCESSED_ARTICLES}")
                article_obj = ProcessedArticle(
                    uuid=message_id,
                    title=article['title'],
                    content=article['content'],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    analysis_results=analysis_message
                )
                await push_to_queue(queue_processed_articles, json.dumps(asdict(article_obj)))

        except Exception as e:
            logger.error(f"[Analyser_Trading_View][{message_id}] Error processing message: {e}", exc_info=True)
            if not message.channel.is_closed:
                await message.reject(requeue=False)
            else:
                logger.warning("[Analyser_Trading_View][{message_id}] Cannot reject message — channel already closed.")



def mq_connect(name) -> pika.BlockingConnection:
    print("[Analyser_Trading_View] Connecting to RabbitMQ...")
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    username = os.getenv("RABBITMQ_USER", "admin")
    password = os.getenv("RABBITMQ_PASS", "password")
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=host,
            heartbeat=600,
            credentials=pika.PlainCredentials(username, password)
        ))
    print("[Analyser_Trading_View] Connected to RabbitMQ.")
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_TV_ARTICLES)
    # Graceful shutdown handler
    def signal_handler(sig, frame):
        print("[Analyser_Trading_View] Gracefully shutting down...")
        channel.stop_consuming()
        connection.close()

    signal.signal(signal.SIGINT, signal_handler)  # Catch Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Catch termination signal
    return connection

async def main():
    connection, queue = await mq_connect(QUEUE_TV_ARTICLES)

    # Declare response queues
    queue_processed_articles = await queue.channel.declare_queue(QUEUE_PROCESSED_ARTICLES, durable=True)

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
    if os.getenv("DEEPSEEK_API_KEY") is None:
        raise ValueError("DEEPSEEK_API_KEY is not set")
    if not os.path.exists(this_dir / "prompt.txt"):
        raise ValueError("Prompt file not found")
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
                analysis_push_gateway=analysis_push_gateway,
                queue_processed_articles=queue_processed_articles))

    events = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, events.set)

    logger.info("Consumer started, waiting for messages")
    await events.wait()

    logger.info("Shutting down")
    await connection.close()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())