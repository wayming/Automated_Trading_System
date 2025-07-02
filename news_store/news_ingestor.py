from .mq_consumer import RabbitMQConsumer
from .weaviate_writer import WeaviateClient

QUEUE_ANALYSIS_OUTPUT = "analysis_output"

class NewsIngestor:
    def __init__(self, mq_host, queue_name, weaviate_config):
        self.consumer = RabbitMQConsumer(mq_host, queue_name)
        self.weaviate = WeaviateClient(**weaviate_config)

    def start(self):
        print("🟢 NewsIngestor started. Waiting for messages...")
        for message in self.consumer.consume():
            self.process_message(message)

    def process_message(self, message):
        print(f"📩 Received message: {message}")
        try:
            news_data = self.parse_news(message)
            self.weaviate.store_news(news_data)
            print("✅ Stored in Weaviate")
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def parse_news(self, raw_message):
        # 假设消息是 JSON 格式
        import json
        return json.loads(raw_message)

def main():
    weaviate_config = {
        "url": "http://localhost:50054",
        "class_name": "NewsArticle"
    }

    ingestor = NewsIngestor("rabbitmq", QUEUE_ANALYSIS_OUTPUT, weaviate_config)
    ingestor.start()

if __name__ == "__main__":
    main()