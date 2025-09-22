import pytest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from common.mq_consumer import RabbitMQConsumer
import asyncio
from contextlib import asynccontextmanager
from common.logger import SingletonLoggerSafe

SingletonLoggerSafe("output/tests/mq_consumer_test.log")
@pytest.fixture
def consumer():
    consumer = RabbitMQConsumer(
        {"host": "localhost",
        "queue_name": "test",
        "username": "guest",
        "password": "guest"})
    return consumer

@pytest.mark.asyncio
async def test_connect_success(consumer):
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_queue.return_value = mock_queue

    with mock.patch("common.mq_consumer.aio_pika.connect_robust", return_value=mock_connection):
        await consumer.connect()

    assert consumer.connection == mock_connection
    assert consumer.channel == mock_channel
    assert consumer.queue == mock_queue
    mock_connection.channel.assert_awaited()
    mock_channel.declare_queue.assert_awaited()

@pytest.mark.asyncio
async def test_consume_multi_handlers(consumer):   
    # fake message
    fake_message1 = MagicMock()
    fake_message1.body.decode.return_value = "msg1"
    fake_message1.process.return_value = AsyncMock()
    fake_message2 = MagicMock()
    fake_message2.body.decode.return_value = "msg2"
    fake_message2.process.return_value = AsyncMock()

    async def message_iter():
        yield fake_message1
        yield fake_message2
    
    @asynccontextmanager
    async def fake_iterator():
        yield message_iter()
    
    consumer.queue = AsyncMock()
    consumer.queue.iterator = fake_iterator

    handler1 = AsyncMock()
    handler2 = AsyncMock()
    consumer.with_handler(handler1)
    consumer.with_handler(handler2)

    task = asyncio.create_task(consumer.consume())
    await asyncio.sleep(0.05)
    consumer.stop_event.set()
    await task

    handler1.assert_has_calls([mock.call("msg1"), mock.call("msg2")])
    handler2.assert_has_calls([mock.call("msg1"), mock.call("msg2")])

@pytest.mark.asyncio
async def test_shutdown(consumer):
    consumer.queue = MagicMock()
    consumer.channel = AsyncMock()
    consumer.connection = AsyncMock()
    consumer.stop_event = MagicMock()
    
    await consumer.shutdown()

    consumer.stop_event.set.assert_called()
    consumer.channel.close.assert_awaited()
    consumer.connection.close.assert_awaited()
