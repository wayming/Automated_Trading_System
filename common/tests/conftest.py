import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_aio_pika(mocker):
    """Fixture: mock aio_pika.connect_robust"""
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()

    # chain return value
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_queue.return_value = mock_queue

    mocker.patch("aio_pika.connect_robust", return_value=mock_connection)

    return {
        "connection": mock_connection,
        "channel": mock_channel,
        "queue": mock_queue,
    }
