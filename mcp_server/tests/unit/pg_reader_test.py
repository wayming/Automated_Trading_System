import pytest
from unittest.mock import AsyncMock
from common.pg_common import PostgresConfig
from mcp_server.pg_reader import PGReader
from mcp.types import ToolResult

@pytest.fixture
async def pg_reader():
    config = PostgresConfig(
        host="localhost",
        port=5432,
        user="user",
        password="pass",
        database="db"
    )

    fake_row = {
        "article_id": "test_001",
        "time": "2025-09-22T12:00:00",
        "title": "Test Title",
        "content": "Test Content",
        "analysis": "OK",
        "error": ""
    }

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [fake_row]
    mock_pool = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch.assert_awaited_once()

    reader = PGReader(config)
    reader.pool = mock_pool
    return reader

@pytest.mark.asyncio
async def test_get_article_historical_analysis_tool_single_row(pg_reader):

    tool = pg_reader.get_article_historical_analysis_tool()
    result: ToolResult = await tool({"article_id": "test_001"})

    pg_reader.conn.fetch.assert_awaited_once()
    assert result.content[0]["data"]["article_id"] == "test_001"

@pytest.mark.asyncio
async def test_get_article_historical_analysis_tool_no_data(pg_reader):
    tool = pg_reader.get_article_historical_analysis_tool()
    result: ToolResult = await tool({"article_id": "missing_id"})

    pg_reader.conn.fetch.assert_awaited_once()
    assert result.content[0]["error"] == "No data found for missing_id"
