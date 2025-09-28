import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from common.pg_common import PostgresConfig
from mcp_server.pg_reader import PGReader

@pytest_asyncio.fixture
async def article_query():

    fake_rows = [
        {
            "article_id": "test_001",
            "time": "2025-09-22T12:00:00",
            "title": "Test Title",
            "content": "Test Content",
            "analysis": "OK",
            "error": ""
        }
    ]
    return lambda sql, *params: [row for row in fake_rows if row["article_id"] == params[0]]

@pytest_asyncio.fixture
async def pg_reader(article_query):
    config = PostgresConfig(
        host="localhost",
        port=5432,
        user="user",
        password="pass",
        database="db"
    )

    reader = PGReader(config)
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = article_query

    mock_acquire = MagicMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_acquire.__aexit__.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acquire
    reader.pool = mock_pool

    return reader

@pytest.mark.asyncio
async def test_get_article_historical_analysis_single_row(pg_reader):
    analysis = await pg_reader.get_article_historical_analysis("test_001")
    assert len(analysis) == 1
    assert analysis[0]["article_id"] == "test_001"

@pytest.mark.asyncio
async def test_get_article_historical_analysis_no_data(pg_reader):
    analysis = await pg_reader.get_article_historical_analysis("test_002")
    assert len(analysis) == 0
