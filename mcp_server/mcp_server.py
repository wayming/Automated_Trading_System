import os
import asyncio
from typing import Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from common.logger import SingletonLoggerSafe
from fastmcp import FastMCP
from fastmcp.tools.tool_manager import ToolManager
from fastmcp.tools.tool import Tool
from common.pg_common import PostgresConfig
from common.wv_common import WeaviateConfig
from mcp_server.pg_reader import PGReader
from mcp_server.wv_reader import WVReader

SingletonLoggerSafe("output/mcp_server.log")

class StockMCPServer(FastMCP):
    """Article Server"""
    
    def __init__(self):
        super().__init__(name="stock-data-mcp-server", version="1.0.0")
        self.logger = SingletonLoggerSafe.component("StockMCPServer")
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
        self.tool_manager.add_tool(Tool.from_function(
            name="get_similar_articles",
            description="Get similar articles",
            fn=self.wv_reader.get_similar_articles,
            output_schema={"type": "list", "items": {"type": "object"}} 
        ))
        self.tool_manager.add_tool(Tool.from_function(
            name="get_article_historical_analysis",
            description="Get article historical analysis",
            fn=self.pg_reader.get_article_historical_analysis,
            output_schema={"type": "list", "items": {"type": "object"}}
        ))
        self.tool_manager.add_tool(Tool.from_function(
            name="list_tools",
            description="List all registered tools",
            fn=self._list_tools,
            output_schema={"type": "list", "items": {"type": "object"}}
        ))
        self.logger.info("StockMCPServer initialized")
    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        await self.pg_reader.connect()
        await self.wv_reader.connect()
        try:
            yield
        finally:
            await self.pg_reader.disconnect()
            await self.wv_reader.disconnect()

    # @self.tool(name="list_tools", description="List all registered tools")
    def _list_tools(self) -> list[Tool]:
        return self.tool_manager.list_tools()

    # @self.tool(
    #     name="get_similar_articles",
    #     description="Get similar articles",
    #     output_schema=list[Dict[str, Any]]  
    # )
    def _get_similar_articles(self, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        return self.wv_reader.get_similar_articles(params)
    
    # @self.tool(
    #     name="get_article_historical_analysis",
    #     description="Get article historical analysis",
    #     output_schema=list[Dict[str, Any]]
    # )
    def _get_article_historical_analysis(self, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        return self.pg_reader.get_article_historical_analysis(params)
    
async def main():
    server = StockMCPServer()
    async with server.lifespan():
        await server.run_async(transport="http", host="0.0.0.0", port=os.getenv("MCP_SERVER_PORT", 8000))

if __name__ == "__main__":
    asyncio.run(main())