# common.py

import logging
import os
import aio_pika
from typing import Tuple

def new_logger(file_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    logging.basicConfig(
        filename=file_path,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(__name__)



async def new_mq_conn(queue_name: str) -> Tuple[aio_pika.RobustConnection, aio_pika.Queue]:
    connection = await aio_pika.connect_robust(
        host="rabbitmq",
        heartbeat=600,
    )
    channel = await connection.channel()
    queue = await channel.declare_queue(queue_name, durable=True)
    return connection, queue
