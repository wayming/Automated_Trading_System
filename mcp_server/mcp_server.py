import asyncio
import json
import sys
import logging
from typing import Dict, Any, AsyncIterator
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import asdict

# MCP SDK 导入（服务器和客户端）
from mcp.server.fastmcp import FastMCP
from mcp.server.session import ServerSession
from mcp.types import Tool, ToolResult
from common.pg_common import PostgresConfig
from common.wv_common import WeaviateConfig

# MCP 客户端（SDK）
from mcp.client import MCPClient

class StockMCPServer(FastMCP):
    """基于 MCP SDK 的股票 MCP 服务器"""
    
    def __init__(self):
        super().__init__(name="stock-data-mcp-server", version="1.0.0")
        self.pg_reader = PGReader(PostgresConfig(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "password"),
            database=os.getenv("POSTGRES_DB", "postgres")
        ))
        self.wv_reader = WVReader(WeaviateConfig(
            host=os.getenv("WEAVIATE_HOST", "localhost"),
            http_port=os.getenv("WEAVIATE_HTTP_PORT", "8080"),
            grpc_port=os.getenv("WEAVIATE_GRPC_PORT", "8081"),
            class_name=os.getenv("WEAVIATE_CLASS_NAME", "Article")
        ))
        self.add_tool(Tool(
            name="list_tools",
            description="List all registered tools",
            func=self._list_tools
        ))
        self.add_tool(Tool(
            name="get_similar_articles",
            description="Get similar articles",
            func=self.wv_reader.get_similar_articles_tool()
        ))
        self.add_tool(Tool(
            name="get_article_historical_analysis",
            description="Get article historical analysis",
            func=self.pg_reader.get_article_historical_analysis_tool()
        ))


    def _list_tools(self) -> ToolResult:
        return ToolResult(content=[{"type": "text", "text": json.dumps([asdict(tool) for tool in self.tools], ensure_ascii=False, indent=2)}])
    
    async def lifespan(self, session: ServerSession) -> AsyncIterator[None]:
        await self.pg_reader.connect()
        await self.wv_reader.connect()
        try:
            yield
        finally:
            await self.pg_reader.disconnect()
            await self.wv_reader.disconnect()

async def main():
    server = StockMCPServer()
    async with serve_websocket(server, host="0.0.0.0", port=8000):
        await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())