import asyncio
import aio_pika
import json
from common.logger import SingletonLoggerSafe

async def article_publisher(mq_channel: aio_pika.channel.Channel, mq_name: str, in_queue: asyncio.Queue, stop_event:asyncio.Event):
    await mq_channel.declare_queue(mq_name, durable=True)
    while not (stop_event.is_set() and in_queue.empty()): # break when stop_event is set and in_queue is empty, allow queue to drain
        try:
            article = await asyncio.wait_for(in_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            continue
        if article:
            try:
                await SingletonLoggerSafe.ainfo(f"Publishing article: {article['title']}")
                await mq_channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(article).encode()),
                    routing_key=mq_name
                )
            except aio_pika.exceptions.AMQPError as e:
                await SingletonLoggerSafe.aerror(f"Queue error: {e}")
                await in_queue.put(article)
                break
            except Exception as e:
                await SingletonLoggerSafe.aerror(f"Failed to publish article: {e}, return to queue")
                await asyncio.sleep(5)
                await in_queue.put(article)
            finally:
                in_queue.task_done()
            