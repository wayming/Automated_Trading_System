from functools import wraps
from cachetools import LRUCache
from typing import Callable
from common.logger import SingletonLoggerSafe
import os
import asyncio
import aio_pika
import time
import grpc
from selenium.webdriver import Remote as RemoteWebDriver
from selenium.webdriver.chrome.options import Options
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc

MQ_CONNECT_TIMEOUT = 60 # seconds

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


async def new_mq_channel(timeout = MQ_CONNECT_TIMEOUT) -> aio_pika.channel.Channel:
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    username = os.getenv("RABBITMQ_USER", "admin")
    password = os.getenv("RABBITMQ_PASS", "password")

    connection = None
    channel = None
    giveup_time = time.time() + timeout
    while time.time() < giveup_time:
        try:
            connection = await aio_pika.connect_robust(
                host=host,
                login=username,
                password=password,
                heartbeat=600,
            )
            channel = await connection.channel()
            SingletonLoggerSafe.info(f"Connected to RabbitMQ")
            return channel
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to connect to RabbitMQ: {e}")
            await asyncio.sleep(5)
    raise Exception("Failed to connect to RabbitMQ")

async def new_aws_conn(endpoint: str) -> pb2_grpc.AnalysisPushGatewayStub:
    """ Caller needs to handle the exception
    """
    channel = grpc.aio.insecure_channel(endpoint)
    stub = pb2_grpc.AnalysisPushGatewayStub(channel)
    return stub


def new_webdriver(selenium_hub_url: str) -> RemoteWebDriver:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")

    SingletonLoggerSafe.info(f"Using Selenium Hub URL: {selenium_hub_url}")
    driver = RemoteWebDriver(
        command_executor=selenium_hub_url,
        options=options
    )
    return driver

def busy_loop(callable: Callable[[], bool], timeout: int = 1):
    for _ in range(timeout):
        if callable():
            break
        else:
            time.sleep(1)
    raise Exception(f"callable {callable} timeout")

