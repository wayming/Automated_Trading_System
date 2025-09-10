import os
from .mq_consumer import RabbitMQConsumer
from .weaviate_writer import WeaviateClient
import json

from news_model.processed_article import ProcessedArticle
# This module is responsible for ingesting news articles from RabbitMQ and storing them in Weaviate.
QUEUE_PROCESSED_ARTICLES = "processed_articles"

class NewsIngestor:
    def __init__(self, mq_config: RabbitMQConfig, wv_config: WeaviateConfig):
        self.mq_config = mq_config
        self.wv_config = wv_config

    def start(self):
        SingletonLoggerSafe.info("🟢 NewsIngestor started. Waiting for messages...")
        try:
            with RabbitMQConsumer(self.mq_config) as consumer:
                with WeaviateClient(self.wv_config) as weaviate:
                    consumer.with_handler(self.weaviate.store_news)
                    consumer.consume()
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to start NewsIngestor: {e}")

    def process_message(self, message):
        SingletonLoggerSafe.info(f"📩 Received message: {message}")
        try:
            processed = self.parse_news(message)
            self.weaviate.store_news(processed)
            print("✅ Stored in Weaviate")
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def parse_news(self, raw_message):
        data = json.loads(raw_message)
        article = ProcessedArticle(**data)
        return article.__dict__

def main():
    SingletonLoggerSafe("output/news_ingestor.log")
    weaviate_config = WeaviateConfig(
        host=os.getenv("WEAVIATE_HOST", "weaviate"),
        http_port=os.getenv("WEAVIATE_HTTP_PORT", "8080"),
        grpc_port=os.getenv("WEAVIATE_GRPC_PORT", "50051"),
        class_name="ProcessedArticle",
    )
    in_queue = None
    ingestor = NewsIngestor("rabbitmq", QUEUE_PROCESSED_ARTICLES, weaviate_config)
    ingestor.start()

if __name__ == "__main__":
    main()