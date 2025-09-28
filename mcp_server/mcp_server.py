import asyncio
import json
import sys
import logging
from typing import Dict, Any, AsyncIterator
from dataclasses import asdict

from fastmcp import FastMCP
from fastmcp.tools import ToolManager
from common.pg_common import PostgresConfig
from common.wv_common import WeaviateConfig

class StockMCPServer(FastMCP):
    """Article Server"""
    
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
        self.tool_manager = ToolManager()
        self.tool_manager.add_tool_from_fn(
            name="list_tools",
            description="List all registered tools",
            func=self._list_tools
        )
        self.tool_manager.add_tool_from_fn(
            name="get_similar_articles",
            description="Get similar articles",
            func=self.wv_reader.get_similar_articles_tool()
        )
        self.tool_manager.add_tool_from_fn(
            name="get_article_historical_analysis",
            description="Get article historical analysis",
            func=self.pg_reader.get_article_historical_analysis_tool()
        )

    async def lifespan(self, session: ServerSession) -> AsyncIterator[None]:
        await self.pg_reader.connect()
        await self.wv_reader.connect()
        try:
            yield
        finally:
            await self.pg_reader.disconnect()
            await self.wv_reader.disconnect()

    @FastMCP.tool(name="list_tools", description="List all registered tools")
    def _list_tools(self) -> list[tool]:
        return self.tool_manager.list_tools()
    
    @FastMCP.tool(name="get_similar_articles", description="Get similar articles")
    def _get_similar_articles(self, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        return self.wv_reader.get_similar_articles(params)
    
    @FastMCP.tool(name="get_article_historical_analysis", description="Get article historical analysis")
    def _get_article_historical_analysis(self, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        return self.pg_reader.get_article_historical_analysis(params)
    
async def main():
    server = StockMCPServer()
    async with serve_websocket(server, host="0.0.0.0", port=8000):
        await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())