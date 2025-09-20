import os
from .mq_consumer import RabbitMQConsumer
from .weaviate_writer import WeaviateClient
from contextlib import AsyncExitStack
import json

from news_model.message import ArticlePayload
# This module is responsible for ingesting news articles from RabbitMQ and storing them in Weaviate.
QUEUE_PROCESSED_ARTICLES = "processed_articles"

# class NewsIngestor:
#     def __init__(self, mq_config: RabbitMQConfig):
#         self.mq_config = mq_config

#     def start(self):
#         SingletonLoggerSafe.info("🟢 NewsIngestor started. Waiting for messages...")
#         try:
#             with RabbitMQConsumer(self.mq_config) as consumer:
#                 with WeaviateClient(self.wv_config) as weaviate:
#                     consumer.with_handler(self.weaviate.store_article)
#                     consumer.consume()
#         except Exception as e:
#             SingletonLoggerSafe.error(f"Failed to start NewsIngestor: {e}")

    # def process_message(self, message):
    #     SingletonLoggerSafe.info(f"📩 Received message: {message}")
    #     try:
    #         processed = self.parse_news(message)
    #         self.weaviate.store_news(processed)
    #         print("✅ Stored in Weaviate")
    #     except Exception as e:
    #         print(f"❌ Error processing message: {e}")

    # def parse_news(self, raw_message):
    #     data = json.loads(raw_message)
    #     article = ArticlePayload(**data)
    #     return article.__dict__

async def main():
    SingletonLoggerSafe("output/news_ingestor.log")

    weaviate_config = WeaviateConfig(
        host=os.getenv("WEAVIATE_HOST", "weaviate"),
        http_port=os.getenv("WEAVIATE_HTTP_PORT", "8080"),
        grpc_port=os.getenv("WEAVIATE_GRPC_PORT", "50051"),
        class_name="ProcessedArticle",
    )

    mq_config = RabbitMQConfig(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        queue_name=QUEUE_PROCESSED_ARTICLES,
    )

    with AsyncExitStack() as stack:
        wv_client = stack.enter_context(WeaviateClient(weaviate_config))
        mq_consumer = stack.enter_context(RabbitMQConsumer(mq_config))

        mq_consumer.with_handler(wv_client.store_article)
        await mq_consumer.consume()

if __name__ == "__main__":
    asyncio.run(main())