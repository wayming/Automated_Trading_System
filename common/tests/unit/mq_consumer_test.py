import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from common.mq_consumer import RabbitMQConsumer

@pytest.mark.asyncio
async def test_connect_success(mock_aio_pika):
    consumer = RabbitMQConsumer({"host": "localhost", "queue_name": "test"})
    await consumer.connect()

    # 用 fixture 提供的 mock 对象做断言
    mock_aio_pika["connection"].channel.assert_called_once()
    mock_aio_pika["channel"].declare_queue.assert_called_once_with("test", durable=True)
    assert consumer.queue == mock_aio_pika["queue"]

@pytest.mark.asyncio
async def test_with_handler_and_consume(mock_aio_pika):
    consumer = RabbitMQConsumer({"host": "localhost", "queue_name": "test"})
    consumer.queue = mock_aio_pika["queue"]

    # 构造假消息
    fake_message1 = MagicMock()
    fake_message1.body.decode.return_value = "msg1"
    fake_message1.process.return_value = AsyncMock()
    fake_message2 = MagicMock()
    fake_message2.body.decode.return_value = "msg2"
    fake_message2.process.return_value = AsyncMock()

    async def fake_iter():
        yield fake_message1
        yield fake_message2
    consumer.queue.iterator = AsyncMock(return_value=fake_iter())

    handler = MagicMock()
    consumer.with_handler(handler)

    task = asyncio.create_task(consumer.consume())
    await asyncio.sleep(0.05)
    consumer.stop_event.set()
    await task

    handler.assert_any_call("msg1")
    handler.assert_any_call("msg2")
    assert handler.call_count == 2

@pytest.mark.asyncio
async def test_shutdown(mock_aio_pika):
    consumer = RabbitMQConsumer({"host": "localhost", "queue_name": "test"})
    consumer.queue = mock_aio_pika["queue"]
    consumer.channel = mock_aio_pika["channel"]
    consumer.connection = mock_aio_pika["connection"]

    await consumer.shutdown()

    consumer.queue.cancel.assert_awaited()
    consumer.channel.close.assert_awaited()
    consumer.connection.close.assert_awaited()
