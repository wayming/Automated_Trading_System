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
        self.model = SentenceTransformer("BAAI/bge-base-zh-v1.5")

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
            try:
                article_title = params["article_title"]
                article_content = params["article_content"]
                
                if article_content is None or article_content == "":
                    results = {"error": "Article content is empty"}
                    return ToolResult(content=[{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}])
                
                embedding = self.model.encode(article_content)
                collection = await self.client.collections.get(self.config["class_name"])
                
                query_result = await collection.query.near_vector(
                    vector=embedding,
                    limit=5
                )

                if not query_result:
                    results = {"error": f"No data found for {article_id}"}
                    return ToolResult(content=[{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}])
            
                results = [obj.properties for obj in query_result.objects]
                return ToolResult(content=[{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}])
            except Exception as e:
                await self.logger.aerror(f"Failed to get similar articles: {e}")
                results = {"error": str(e)}
                return ToolResult(content=[{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}])
    
        return get_similar_articles
