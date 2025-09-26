import json
from typing import Dict, Any
from mcp.types import Tool, ToolResult
from common.logger import SingletonLoggerSafe
from common.pg_common import asyncpg
from typing import TypedDict

class WeaviateConfig(TypedDict):
    host: str
    http_port: str
    grpc_port: str
    class_name: str

class WVReader:
    def __init__(self, config: WeaviateConfig):
        self.config = config
        self.logger = SingletonLoggerSafe.component("WVReader")
        self.client = None

    async def connect(self):
        try:
            self.client = weaviate.WeaviateAsyncClient(
            connection_params=ConnectionParams.from_params(
                http_host=self.config["host"],
                http_port=self.config["http_port"],
                http_secure=False,
                grpc_host=self.config['host'],
                grpc_port=self.config["grpc_port"],
                grpc_secure=False,
                )
            )
            await self.client.connect()
            await self.logger.ainfo(f"Connected to Weaviate at {self.config['host']}:{self.config['http_port']}")
        except Exception as e:
            await self.logger.aerror(f"Failed to connect to Weaviate: {e}")
            raise e
    
    async def disconnect(self):
        try:
            await self.client.close()
            await self.logger.ainfo(f"Disconnected from Weaviate at {self.config['host']}:{self.config['http_port']}")
        except Exception as e:
            await self.logger.aerror(f"Failed to disconnect from Weaviate: {e}")
            raise e

    def get_similar_articles_tool(self) -> Tool:
        """define get_similar_articles tool"""
        @self.tool(
            name="get_similar_articles",
            description="get similar articles",
            parameters={
                "type": "object",
                "properties": {
                    "article_title": {"type": "string", "description": "article title"},
                    "article_content": {"type": "string", "description": "article content"}
                },
                "required": ["article_title", "article_content"]
            }
        )

        async def get_similar_articles(params: Dict[str, Any]) -> ToolResult:
            article_title = params["article_title"]
            article_content = params["article_content"]
            
            with self.client.acquire() as conn:
                rows = await conn.fetch("""
                SELECT article_id, time, title, content, analysis, error
                FROM articles
                WHERE article_id = %s
            """, [article_id])
            
            if not rows:
                result = {"error": f"No data found for {article_id}"}
            elif len(rows) > 1:
                result = {"error": f"Multiple data found for {article_id}"}
            else:
                result = rows[0]
            
            return ToolResult(content=[{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}])

        return get_similar_articles
