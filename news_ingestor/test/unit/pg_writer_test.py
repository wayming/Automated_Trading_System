import pytest
from unittest import mock
from dataclasses import asdict
from news_model.message import ArticlePayload
from news_ingestor.pg_writer import PostgresWriter, PostgresConfig
from common.logger import SingletonLoggerSafe
from datetime import datetime
# -------------------------
# pytest fixtures
# -------------------------
@pytest.fixture
def article_json_str():
    # Sample article JSON string
    return """
    {
        "article_id": "test_001",
        "time": "2025-09-22T12:00:00Z",
        "title": "Test Title",
        "content": "This is a test content.",
        "analysis": "OK",
        "error": ""
    }
    """

@pytest.fixture
def article_obj(article_json_str):
    # Convert JSON string to ArticlePayload object
    return ArticlePayload.from_json(article_json_str)

@pytest.fixture
def mock_config():
    # Mock Postgres configuration
    return PostgresConfig(
        host="mock_host",
        port=5432,
        user="mock_user",
        password="mock_password",
        database="mock_db",
        table_name="mock_table"
    )

@pytest.fixture
def writer(mock_config):
    # Create PostgresWriter instance with mocked connection
    w = PostgresWriter(mock_config)
    w.conn = mock.AsyncMock()
    return w

SingletonLoggerSafe("output/tests/pg_writer_test.log")

# -------------------------
# Tests
# -------------------------
@pytest.mark.asyncio
async def test_store_article(writer, article_json_str, article_obj):
    # Patch from_json method to return the pre-created article object
    with mock.patch.object(ArticlePayload, "from_json", return_value=article_obj):
        await writer.store_article(article_json_str)

    # Check that conn.execute was called
    writer.conn.execute.assert_awaited(), "Expected conn.execute to be called"

    # Verify SQL parameters include article data
    sql_call_args = writer.conn.execute.call_args[0][0]
    values_call_args = writer.conn.execute.call_args[0][1:]
    for key, val in asdict(article_obj).items():
        if key in writer.table_defn:
            if writer.table_defn[key]['type'] == "timestamp":
                assert datetime.fromisoformat(val) in values_call_args or val is None
            else:
                assert str(val) in str(values_call_args) or val is None

@pytest.mark.asyncio
async def test___ensure_table(writer, mock_config):
    # Call _ensure_table to create table if it does not exist
    await writer._ensure_table()

    # Verify that conn.execute was called to create the table
    writer.conn.execute.assert_awaited(), "Expected execute to be called to create table"

    # Check that SQL statement contains table name and all fields
    sql_call_args = writer.conn.execute.call_args[0][0]
    assert mock_config["table_name"] in sql_call_args
    for field in ["article_id", "time", "title", "content", "analysis", "error"]:
        assert field in sql_call_args
