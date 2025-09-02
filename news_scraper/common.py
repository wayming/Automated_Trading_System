# common.py

import logging
import os
import aio_pika
import signal
import grpc.aio
from typing import Optional
from cachetools import LRUCache
from functools import wraps
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc

_logger: Optional[logging.Logger] = None
def get_logger(file_path: Optional[str] = None) -> logging.Logger:
    global _logger
    if _logger:
        return _logger

    if not file_path:
        raise ValueError("file_path is required")
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    logger = logging.getLogger(file_path) # Single instance
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        ch.setFormatter(ch_formatter)
        logger.addHandler(ch)

        # File handler
        fh = logging.FileHandler(file_path)
        fh.setLevel(logging.INFO)
        fh_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fh_formatter)

        logger.addHandler(fh)
        logger.propagate = False     # Prevent double logging
    _logger = logger
    return logger

def log_section(logger: logging.Logger, section: str):
    line = "#" * 50
    logger.info(line)
    logger.info("#  " + section)
    logger.info(line)
    
async def new_mq_channel(queue_name: str) -> aio_pika.channel.Channel:
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    username = os.getenv("RABBITMQ_USER", "admin")
    password = os.getenv("RABBITMQ_PASS", "password")
    logger = get_logger()

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
            logger.info(f"Connected to RabbitMQ and declared queue '{queue_name}'")
            return channel
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
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
