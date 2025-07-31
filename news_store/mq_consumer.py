import pika
from news_model.processed_article import ProcessedArticle

class RabbitMQConsumer:
    def __init__(self, mq_host, queue_name):
        self.queue_name = queue_name
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=mq_host))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue_name, durable=True)

    def consume(self):
        for method_frame, properties, body in self.channel.consume(self.queue_name, inactivity_timeout=1):
            if body:
                yield body.decode()
                self.channel.basic_ack(method_frame.delivery_tag)