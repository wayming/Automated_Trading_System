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

LIST_OF_OBJECTS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "object"}
        }
    },
    "required": ["items"]
}

class StockMCPServer:
    def __init__(self):
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
            class_name=os.getenv("WEAVIATE_CLASS_NAME", "articles")
        ))

    async def __aenter__(self):
        await self.pg_reader.connect()
        await self.wv_reader.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pg_reader.disconnect()
        await self.wv_reader.disconnect()

    def register_tools(self, mcp: FastMCP):
        @mcp.tool (
            name="get_similar_articles",
            description="Get similar articles",
            output_schema=LIST_OF_OBJECTS_SCHEMA
        )
        async def get_similar_articles(article_content: str) -> Dict[str, Any]:
            return {"items": await self.wv_reader.get_similar_articles(article_content)}
        
        @mcp.tool (
            name="get_article_historical_analysis",
            description="Get article historical analysis",
            output_schema=LIST_OF_OBJECTS_SCHEMA
        )
        async def get_article_historical_analysis(article_id: str) -> Dict[str, Any]:
            return {"items": await self.pg_reader.get_article_historical_analysis(article_id)}
        
        @mcp.tool (
            name="list_tools",
            description="List all registered tools",
            output_schema=LIST_OF_OBJECTS_SCHEMA
        )
        async def list_tools() -> Dict[str, Any]:
            return {"items": mcp.tools.list_tools()}
    
async def main():
    async with StockMCPServer() as server:
        mcp = FastMCP()
        server.register_tools(mcp)
        await mcp.run_async(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_SERVER_PORT", 8000)))

if __name__ == "__main__":
    asyncio.run(main())

