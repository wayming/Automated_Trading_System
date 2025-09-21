import os
from common.mq_consumer import RabbitMQConsumer
from .weaviate_writer import WeaviateClient, WeaviateConfig
from contextlib import AsyncExitStack
import asyncio
from common.logger import SingletonLoggerSafe
from common.mq_consumer import RabbitMQConfig

# This module is responsible for ingesting news articles from RabbitMQ and storing them in Weaviate.
QUEUE_PROCESSED_ARTICLES = "processed_articles"

async def main():
    SingletonLoggerSafe("output/news_ingestor.log")

    weaviate_config = WeaviateConfig(
        host=os.getenv("WEAVIATE_HOST", "weaviate"),
        http_port=os.getenv("WEAVIATE_HTTP_PORT", "8080"),
        grpc_port=os.getenv("WEAVIATE_GRPC_PORT", "50051"),
        class_name="articles",
    )
    SingletonLoggerSafe.info(f"Connecting to Weaviate at {weaviate_config['host']}:{weaviate_config['http_port']}")

    mq_config = RabbitMQConfig(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        username=os.getenv("RABBITMQ_USER", "admin"),
        password=os.getenv("RABBITMQ_PASS", "password"),
        queue_name=QUEUE_PROCESSED_ARTICLES,
    )
    SingletonLoggerSafe.info(f"Connecting to RabbitMQ at {mq_config['host']}:{mq_config['queue_name']}")

    async with AsyncExitStack() as stack:
        wv_client = await stack.enter_async_context(WeaviateClient(weaviate_config))
        mq_consumer = await stack.enter_async_context(RabbitMQConsumer(mq_config))

        mq_consumer.with_handler(wv_client.store_article)
        await mq_consumer.consume() # wait until stop_event is set

if __name__ == "__main__":
    asyncio.run(main())