# common.py

import logging
import os
import aio_pika
import pika
from typing import Tuple
import signal
import grpc.aio
from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc


def new_logger(file_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    logger = logging.getLogger(file_path) # Single instance
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        ch.setFormatter(ch_formatter)

        # File handler
        fh = logging.FileHandler(file_path)
        fh.setLevel(logging.INFO)
        fh_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fh_formatter)

        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger

async def new_mq_conn(queue_name: str) -> Tuple[aio_pika.RobustConnection, aio_pika.Queue]:
    """ Caller needs to handle the exception
    """

    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    username = os.getenv("RABBITMQ_USER", "admin")
    password = os.getenv("RABBITMQ_PASS", "password")
    
    connection = await aio_pika.connect_robust(
        host=host,
        login=username,
        password=password,
        heartbeat=600,
    )
    channel = await connection.channel()
    queue = await channel.declare_queue(queue_name, durable=True)

    # Graceful shutdown handler
    def signal_handler(sig, frame):
        print("[Analyser_Trading_View] Gracefully shutting down...")
        channel.stop_consuming()
        connection.close()

    signal.signal(signal.SIGINT, signal_handler)  # Catch Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Catch termination signal
    return connection, queue


    
async def new_aws_conn(endpoint: str):
    """ Caller needs to handle the exception
    """
    channel = grpc.aio.insecure_channel(endpoint)
    stub = pb2_grpc.AnalysisPushGatewayStub(channel)
    return stub