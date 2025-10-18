import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sentence_transformers import SentenceTransformer
from mcp_server.wv_reader import WVReader, WeaviateConfig


@pytest.fixture
def config():
    return WeaviateConfig(
        host="localhost",
        http_port="8080",
        grpc_port="50051",
        class_name="Article"
    )

@pytest.mark.asyncio
async def test_connect_and_disconnect(config):
    reader = WVReader(config)

    mock_client = AsyncMock()
    with patch("weaviate.WeaviateAsyncClient", return_value=mock_client):
        await reader.connect()
        mock_client.connect.assert_awaited_once()

        await reader.disconnect()
        mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_similar_articles_success(config):
    reader = WVReader(config)

    # mock model.encode
    with patch.object(SentenceTransformer, "encode", return_value=[0.1, 0.2, 0.3]):
        # mock weaviate client
        mock_collection = AsyncMock()
        mock_collection.query.near_vector.return_value.objects = [
            MagicMock(properties={"id": 1, "title": "Test"})
        ]

        mock_client = AsyncMock()
        mock_client.collections.get.return_value = mock_collection
        reader.client = mock_client

        result = await reader.get_similar_articles("Some text here")

        assert result == [{"id": 1, "title": "Test"}]
        mock_collection.query.near_vector.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_similar_articles_empty_content(config):
    reader = WVReader(config)

    result = await reader.get_similar_articles("   ")

    assert result == []


@pytest.mark.asyncio
async def test_get_similar_articles_no_results(config):
    reader = WVReader(config)

    with patch.object(SentenceTransformer, "encode", return_value=[0.1, 0.2, 0.3]):
        mock_collection = AsyncMock()
        mock_collection.query.near_vector.return_value.objects = []

        mock_client = AsyncMock()
        mock_client.collections.get.return_value = mock_collection
        reader.client = mock_client

        result = await reader.get_similar_articles("Some text")

        assert result == []
