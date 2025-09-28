import json
from typing import Dict, Any, TypedDict
from mcp.server.fastmcp import tool
from mcp.types import CallToolResult
from common.logger import SingletonLoggerSafe
import weaviate
from weaviate.classes.init import ConnectionParams
from sentence_transformers import SentenceTransformer


class WeaviateConfig(TypedDict):
    host: str
    http_port: str
    grpc_port: str
    class_name: str


class WVReader:
    def __init__(self, config: WeaviateConfig):
        self.config = config
        self.logger = SingletonLoggerSafe.component("WVReader")
        self.client: weaviate.WeaviateAsyncClient | None = None
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
            await self.logger.ainfo(
                f"Connected to Weaviate at {self.config['host']}:{self.config['http_port']}"
            )
        except Exception as e:
            await self.logger.aerror(f"Failed to connect to Weaviate: {e}")
            raise

    async def disconnect(self):
        try:
            if self.client:
                await self.client.close()
            await self.logger.ainfo(
                f"Disconnected from Weaviate at {self.config['host']}:{self.config['http_port']}"
            )
        except Exception as e:
            await self.logger.aerror(f"Failed to disconnect from Weaviate: {e}")
            raise

    async def get_similar_articles(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search similar articles in Weaviate based on embedding"""
        try:
            article_title = params["article_title"]
            article_content = params["article_content"]

            if not article_content.strip():
                self.logger.ainfo("Article content is empty")
                return []

            embedding = self.model.encode(article_content)
            collection = await self.client.collections.get(self.config["class_name"])

            query_result = await collection.query.near_vector(
                vector=embedding,
                limit=5
            )

            if not query_result or not query_result.objects:
                self.logger.ainfo("No similar articles found for {article_title}")
                return []

            return [obj.properties for obj in query_result.objects]

        except Exception as e:
            await self.logger.aerror(f"Failed to get similar articles: {e}")
            raise e
