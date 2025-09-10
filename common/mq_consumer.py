import asyncio
from typing import List, Callable
import aio_pika
from common.logger import SingletonLoggerSafe
from typing import TypedDict

class RabbitMQConfig(TypedDict):
    host: str
    queue_name: str
    
class RabbitMQConsumer:
    def __init__(self, config: RabbitMQConfig):
        self.config = config
        self.connection = None
        self.channel = None
        self.queue = None
        self.consumer = None
        self.handlers: List[Callable[[str], None]] = []
        self.stop_event = asyncio.Event()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(
                host=self.config["host"],
                heartbeat=60,
            )
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue(
                self.config["queue_name"],
                durable=True,
            )
        except Exception as e:
            raise Exception(f"Failed to connect to RabbitMQ: {e}")
    
    async def shutdown(self):
        if self.stop_event:
            try:
                self.stop_event.set()
            except Exception as e:
                SingletonLoggerSafe.error(f"Failed to set stop event: {e}")
        if self.consumer:
            try:
                await self.consumer.cancel()
            except Exception as e:
                SingletonLoggerSafe.error(f"Failed to cancel consumer: {e}")
        if self.channel:
            try:
                await self.channel.close()
            except Exception as e:
                SingletonLoggerSafe.error(f"Failed to close channel: {e}")
        if self.connection:
            try:
                await self.connection.close()
            except Exception as e:
                SingletonLoggerSafe.error(f"Failed to close connection: {e}")
        
    def with_handler(self, handler):
        self.handlers.append(handler)
        return self

    async def consume(self):
        if self.queue is None:
            raise Exception("Queue not initialized")
        
        if self.handlers is None or len(self.handlers) == 0:
            raise Exception("No handlers registered")
        
        try:
            self.consumer = await self.queue.consume(self._handler_wrapper())
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to consume: {e}")
            raise
            
        await self.stop_event.wait()

    def _handler_wrapper(self):
        def wrapper(raw_message: aio_pika.IncomingMessage):
            message = raw_message.body.decode("utf-8")
            for handler in self.handlers:
                try:
                    handler(message)
                except Exception as e:
                    SingletonLoggerSafe.error(f"Handler failed: {e}")
        return wrapper