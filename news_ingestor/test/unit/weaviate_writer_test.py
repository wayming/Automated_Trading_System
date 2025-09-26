import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from news_ingestor.weaviate_writer import WeaviateWriter, WeaviateConfig
from common.logger import SingletonLoggerSafe

logger = SingletonLoggerSafe("output/tests/weaviate_writer_test.log")

@pytest.fixture
def mock_config():
    return WeaviateConfig(
                host="localhost",
                http_port="8080",
                grpc_port="50051",
                class_name="Article",
    )

@pytest.fixture
def writer(mock_config):
    w = WeaviateWriter(mock_config)
    w.client = AsyncMock()
    return w

@pytest.mark.asyncio
async def test_connect_and_disconnect(writer):
    mock_client = AsyncMock()
    with patch("weaviate.WeaviateAsyncClient", return_value=mock_client):
        async with writer:
            mock_client.connect.assert_awaited_once()
            mock_client.collections.exists.assert_awaited_with("Article")
        mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_article_success(writer):
    mock_client = AsyncMock()
    mock_collection = AsyncMock()
    mock_client.collections.get.return_value = mock_collection
    await logger.ainfo("Testing store article success")

    fake_article = MagicMock()
    fake_article.article_id = "123"
    fake_article.content = "测试文章"
    
    with patch("weaviate.WeaviateAsyncClient", return_value=mock_client), \
         patch("news_ingestor.weaviate_writer.SentenceTransformer") as mock_model_cls, \
         patch("news_ingestor.weaviate_writer.ArticlePayload") as mock_article_cls:

        mock_model = MagicMock()
        mock_model.encode.return_value = [0.1, 0.2, 0.3]
        mock_model_cls.return_value = mock_model
        mock_article_cls.from_json.return_value = fake_article

        await writer.store_article('{"article_id": "123", "content": "测试文章"}')

        mock_model.encode.assert_called_once_with("测试文章")
        mock_collection.data.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_article_failure(writer):
    mock_client = AsyncMock()
    mock_collection = AsyncMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("weaviate.WeaviateAsyncClient", return_value=mock_client), \
         patch("news_ingestor.weaviate_writer.ArticlePayload") as mock_article_cls:

        mock_article_cls.from_json.side_effect = ValueError("bad json")

        await writer.store_article("invalid json")
