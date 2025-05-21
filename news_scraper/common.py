# common.py

import logging
import os
import pika

def new_logger(file_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    logging.basicConfig(
        filename=file_path,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(__name__)


def new_mq_conn(queue: str) -> pika.adapters.blocking_connection.BlockingChannel:
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='rabbitmq',
        heartbeat=600
    ))
    channel = connection.channel()
    channel.queue_declare(queue=queue)
    return connection, channel
