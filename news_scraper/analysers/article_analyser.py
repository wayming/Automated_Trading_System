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

from common.interface import NewsAnalyser
from common.logger import SingletonLoggerSafe
from news_model.message import ArticleMessage
from analysers.providers import LLMProvider
from trade_policy import TradePolicy

from langchain_openai import ChatOpenAI, OpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

# This module is responsible for analyzing trading view articles using DeepSeek's LLM.

# timeout for push to AWS
TIMEOUT_PUSH_TO_AWS = 600

class ArticleAnalyser(NewsAnalyser):
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.tools = [self.sample_tool]
        self.llm = ChatOpenAI(
            model=provider.model_name,
            temperature=0.0,
            api_key=provider.api_key,
            base_url=provider.base_url,
            tools=self.tools
        )

        self.llm_tools = self.llm.bind_tools(self.tools)
            
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.llm.close()

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

    @tool
    def sample_tool(self):
        """Sample tool"""
        return "Sample tool"
    
    def analyse(self, article_content: str) -> Tuple[Optional[dict], str]:
        with open(self.provider.prompt_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read()

        prompt = f"{base_prompt}\n\n---\n\n{article_content}"
        response = self.llm_tools.invoke(prompt)

        structured_result = self._extract_structured_response(response.content)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"\n\n" + ">"*80 + "\n"
        log_message += f"Timestamp: {timestamp}\n"
        log_message += "Full Response:\n"
        log_message += response.content
        log_message += "\n" + ">"*80 + "\n\n"
        SingletonLoggerSafe.info(log_message)

        return structured_result, response.content

# Push processed article to processed articles queue
async def push_to_processed_queue(queue: aio_pika.Queue, article: ArticleMessage):
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
            article = ArticleMessage.from_json(message.body.decode())
            await SingletonLoggerSafe.ainfo(f"New message received. id={article.message_id}")

            # Analyze message
            await SingletonLoggerSafe.ainfo(f"Analyzing message content...")
            article.response_struct, article.response_raw = await asyncio.to_thread(analyser.analyse, article)

            # Evaluate trade policy
            if article.response_struct is not None:
                await evaluate_trade_policy(trade_policy, article.response_struct)
                await push_to_processed_queue(queue_processed_articles, article)
            else:
                await SingletonLoggerSafe.ainfo(f"[{article.message_id}] response message: {article.response_raw}")
            
            # Push to AWS
            if analysis_push_gateway is not None:
                await push_to_aws_gateway(analysis_push_gateway, TIMEOUT_PUSH_TO_AWS, article.response_raw)

        except Exception as e:
            await SingletonLoggerSafe.aerror(f"[{article.message_id}] Error processing message: {e}", exc_info=True)
            if not message.channel.is_closed:
                await message.reject(requeue=False)
            else:
                await SingletonLoggerSafe.ainfo(f"[{article.message_id}] Cannot reject message — channel already closed.")

async def graceful_shutdown(channel, analyser):
    await SingletonLoggerSafe.ainfo("Shutting down")
    if channel is not None:
        await channel.close()
    if analyser is not None:
        await asyncio.to_thread(analyser.__exit__)
    await SingletonLoggerSafe.ainfo("Shutdown complete")
