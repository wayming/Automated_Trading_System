import time
import asyncio
import aio_pika
import json
from datetime           import datetime
from typing             import Optional, Tuple
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc

from common.interface import NewsAnalyser
from common.logger import SingletonLoggerSafe
from news_model.message import ArticlePayload
from news_analyser.providers import LLMProvider
from news_analyser.trade_policy import TradePolicy
from news_analyser.agent import Agent

# This module is responsible for analyzing trading view articles using DeepSeek's LLM.

# timeout for push to AWS
TIMEOUT_PUSH_TO_AWS = 600

# Push processed article to processed articles queue
async def push_to_processed_queue(queue: aio_pika.Queue, article: ArticlePayload):
    try:
        await SingletonLoggerSafe.ainfo(f"Pushing processed article to queue {queue.name}")
        await queue.channel.default_exchange.publish(
            aio_pika.Message(body=article.to_json().encode()),
            routing_key=queue.name)
        await SingletonLoggerSafe.ainfo(f"Message pushed to queue {queue.name}: {article.to_json()[:80]}...")
    except Exception as e:
        await SingletonLoggerSafe.aerror(f"Failed to push message to queue {queue.name}: {e}")

# Push analysis results to AWS gateway
async def push_to_aws_gateway(analysis_push_gateway: pb2_grpc.AnalysisPushGatewayStub, timeout: int, message: str):
    start = time.time()
    await SingletonLoggerSafe.ainfo(f"Pushing analysis results to AWS at {time.ctime(start)}")
    try:
        response = await asyncio.wait_for(
            analysis_push_gateway.Push(pb2.PushRequest(message=message)),
            timeout=timeout
        )
        await SingletonLoggerSafe.ainfo(f"PushResponse: status_code={response.status_code}, response_text={response.response_text}")
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
        try:
            # Read message
            article = ArticlePayload.from_json(message.body.decode())
            await SingletonLoggerSafe.ainfo(f"New message received. id={article.id}")

            # Analyze message
            await SingletonLoggerSafe.ainfo(f"Analyzing message content...")
            article.analysis, article.error = await analyser.invoke(article.content)
            
            # Evaluate trade policy
            aws_message = ""
            if article.error:
                aws_message = article.error
                await SingletonLoggerSafe.ainfo(f"[{article.id}] error: {article.error}")
            else:
                await evaluate_trade_policy(trade_policy, article.analysis)
                await push_to_processed_queue(queue_processed_articles, article)
                aws_message = json.dumps(article.analysis)
            
            
            # Push to AWS
            if analysis_push_gateway is not None:
                await push_to_aws_gateway(analysis_push_gateway, TIMEOUT_PUSH_TO_AWS, aws_message)

        except Exception as e:
            await SingletonLoggerSafe.aerror(f"[{article.id}] Error processing message: {e}", exc_info=True)
            if not message.channel.is_closed:
                await message.reject(requeue=False)
            else:
                await SingletonLoggerSafe.ainfo(f"[{article.id}] Cannot reject message — channel already closed.")

async def graceful_shutdown(channel):
    await SingletonLoggerSafe.ainfo("Shutting down")
    if channel is not None:
        await channel.close()
    await SingletonLoggerSafe.ainfo("Shutdown complete")
