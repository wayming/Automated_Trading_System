import os
import json
import re
import time
import asyncio
import aio_pika
import signal
from datetime           import datetime, timezone
from typing             import Optional, Tuple
from dataclasses        import asdict
from openai             import OpenAI
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc
import uuid

from .providers import LLMProvider
from news_model.processed_article import ProcessedArticle
from common.logger import SingletonLoggerSafe
from common.interface import NewsAnalyser
from trade_policy import TradePolicy

# This module is responsible for analyzing trading view articles using DeepSeek's LLM.


class ArticleAnalyser(NewsAnalyser):
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.ds_client = None

    def __enter__(self):
        self.ds_client = OpenAI(api_key=self.provider.api_key, base_url=self.provider.base_url)
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds_client.close()

    def _send_to_llm(self, prompt_text):
        response = self.ds_client.chat.completions.create(
            model=self.provider.model_name,
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
            SingletonLoggerSafe.info(f"No structured resposne found from llm response:\n{response_text}")
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            SingletonLoggerSafe.error(f"Failed to decode JSON struct.\n{match.group(1)}\nError: {e}")
            return None

    def analyse(self, html_text: str) -> Tuple[Optional[dict], str]:
        article = self._extract_article(html_text)
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read()

        prompt = f"{base_prompt}\n\n---\n\nTitle: {article['title']}\n\nContent:\n{article['content']}"
        response = self._send_to_llm(prompt)

        structured_result = self._extract_structured_response(response)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"\n\n" + ">"*80 + "\n"
        log_message += f"Timestamp: {timestamp}\n"
        log_message += "Full Response:\n"
        log_message += response
        log_message += "\n" + ">"*80 + "\n\n"
        SingletonLoggerSafe.info(log_message)

        return structured_result, response.strip()

# Push processed article to processed articles queue
async def push_to_processed_queue(queue: aio_pika.Queue, article: dict, message_id: str, message: str):
    try:
        await SingletonLoggerSafe.ainfo(f"Pushing processed article to queue {QUEUE_PROCESSED_ARTICLES}")
        article_obj = ProcessedArticle(
            uuid=message_id,
            title=article['title'],
            content=article['content'],
            timestamp=datetime.now(timezone.utc).isoformat(),
            analysis_results=message)
        await queue.channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(asdict(article_obj)).encode()),
            routing_key=queue.name)
        await SingletonLoggerSafe.ainfo(f"Message pushed to queue {queue.name}: {message[:80]}...")
    except Exception as e:
        await SingletonLoggerSafe.aerror(f"Failed to push message to queue {queue.name}: {e}")

# Push analysis results to AWS gateway
async def push_to_aws_gateway(analysis_push_gateway: pb2_grpc.AnalysisPushGatewayStub, timeout: int, message: str):
    start = time.time()
    await SingletonLoggerSafe.ainfo(f"Pushing analysis results to AWS at {time.ctime(start)}")
    try:
        response = await asyncio.wait_for(
            analysis_push_gateway.push(pb2.PushRequest(message=message)),
            timeout=timeout
        )
        await SingletonLoggerSafe.ainfo(f"PushResponse: status_code=%d, response_text=%s",
                                response.status_code, response.response_text)
    except asyncio.TimeoutError:
        await SingletonLoggerSafe.aerror(f"Push request timed out after {time.time() - start:.2f} seconds, skipping or retrying")
    except Exception as grpc_err:
        await SingletonLoggerSafe.aerror(f"Failed to push to AWS: {grpc_err}")

# Evaluate trade policy
async def evaluate_trade_policy(trade_policy: TradePolicy, struct_result: dict):
    try:
        await SingletonLoggerSafe.ainfo(f"Evaluating trade policy")
        await asyncio.to_thread(trade_policy.evaluate, struct_result)
    except Exception as e:
        await SingletonLoggerSafe.aerror(f"Failed to evaluate trade policy: {e}")

async def consume_message(
        message: aio_pika.IncomingMessage,
        analyser, trade_policy, analysis_push_gateway,
        queue_processed_articles):
    async with message.process(ignore_processed=True):
        message_id=None
        try:
            # Read message
            message_id = str(uuid.uuid4())[:8]
            await SingletonLoggerSafe.ainfo(f"[{message_id}] New message received.")
            article = message.body.decode()

            # Analyze message
            await SingletonLoggerSafe.ainfo(f"[{message_id}] Analyzing message content...")
            struct_result, raw_text = await asyncio.to_thread(analyser.analyse, article)

            # Evaluate trade policy
            analysis_message=None
            if struct_result is not None:
                analysis_message = json.dumps(struct_result, indent=2, ensure_ascii=False)
                await evaluate_trade_policy(trade_policy, struct_result)
                await push_to_processed_queue(queue_processed_articles, analysis_message)
            else:
                analysis_message = raw_text
            
            # Push to AWS
            await SingletonLoggerSafe.ainfo(f"[{message_id}] response message: {analysis_message}")
            if analysis_push_gateway is not None:
                await push_to_aws_gateway(analysis_push_gateway, TIMEOUT_PUSH_TO_AWS, analysis_message)

        except Exception as e:
            await SingletonLoggerSafe.aerror(f"[{message_id}] Error processing message: {e}", exc_info=True)
            if not message.channel.is_closed:
                await message.reject(requeue=False)
            else:
                await SingletonLoggerSafe.ainfo(f"[{message_id}] Cannot reject message — channel already closed.")

async def graceful_shutdown(channel, analyser):
    await SingletonLoggerSafe.ainfo("Shutting down")
    if channel is not None:
        await channel.close()
    if analyser is not None:
        await asyncio.to_thread(analyser.__exit__)
    await SingletonLoggerSafe.ainfo("Shutdown complete")
