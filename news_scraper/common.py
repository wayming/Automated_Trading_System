# common.py

import logging
import os
import aio_pika
import signal
import grpc.aio
import asyncio
from typing import Callable
from cachetools import LRUCache
from functools import wraps
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc
from singleton_logger import SafeSingletonLogger

async def new_mq_channel(queue_name: str) -> aio_pika.channel.Channel:
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    username = os.getenv("RABBITMQ_USER", "admin")
    password = os.getenv("RABBITMQ_PASS", "password")

    connection = None
    channel = None
    while True:
        try:
            connection = await aio_pika.connect_robust(
                host=host,
                login=username,
                password=password,
                heartbeat=600,
            )
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            SafeSingletonLogger.info(f"Connected to RabbitMQ and declared queue '{queue_name}'")
            return channel
        except Exception as e:
            SafeSingletonLogger.error(f"Failed to connect to RabbitMQ: {e}")
            await asyncio.sleep(5)

async def new_aws_conn(endpoint: str):
    """ Caller needs to handle the exception
    """
    channel = grpc.aio.insecure_channel(endpoint)
    stub = pb2_grpc.AnalysisPushGatewayStub(channel)
    return stub

def cached_fetcher(maxsize: int):
    def decorator(func):
        already_processed = LRUCache(maxsize)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if already_processed.get(key):
                return
            result = func(*args, **kwargs)
            already_processed[key] = True
            return result
        return wrapper
    return decorator

def busy_loop(callable: Callable[[], bool], timeout: int = 1):
    for _ in range(timeout):
        if callable():
            break
        else:
            time.sleep(1)
    raise Exception(f"callable {callable} timeout")