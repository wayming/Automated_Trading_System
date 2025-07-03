import os
from .mq_consumer import RabbitMQConsumer
from .weaviate_writer import WeaviateClient

from news_model.processed_article import ProcessedArticle
# This module is responsible for ingesting news articles from RabbitMQ and storing them in Weaviate.
QUEUE_PROCESSED_ARTICLES = "processed_articles"

class NewsIngestor:
    def __init__(self, mq_host, queue_name, wv_config):
        self.consumer = RabbitMQConsumer(mq_host, queue_name)
        self.weaviate = WeaviateClient(wv_config)

    def start(self):
        print("🟢 NewsIngestor started. Waiting for messages...")
        for message in self.consumer.consume():
            self.process_message(message)

    def process_message(self, message):
        print(f"📩 Received message: {message}")
        try:
            processed = self.parse_news(message)
            self.weaviate.store_news(processed)
            print("✅ Stored in Weaviate")
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def parse_news(self, raw_message):
        data = raw_message.decode()
        return ProcessedArticle.parse_raw(data).dict()
    
def main():
    weaviate_config = {
        "host": "weaviate",
        "http_port": os.getenv("WEAVIATE_HTTP_PORT", "8080"),
        "grpc_port": os.getenv("WEAVIATE_GRPC_PORT", "50051"),
        "class_name": "ProcessedArticle",
    }

    ingestor = NewsIngestor("rabbitmq", QUEUE_PROCESSED_ARTICLES, weaviate_config)
    ingestor.start()

if __name__ == "__main__":
    main()