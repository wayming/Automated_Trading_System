import weaviate
from weaviate.connect import ConnectionParams
from weaviate.collections.classes.config import DataType
from typing import TypedDict
from news_model.message import ArticlePayload
from common.logger import SingletonLoggerSafe
from dataclasses import asdict
from sentence_transformers import SentenceTransformer

class WeaviateConfig(TypedDict):
    host: str
    http_port: str
    grpc_port: str
    class_name: str


class WeaviateWriter:
    def __init__(self, config: WeaviateConfig):
        self.config = config
        self.properties = [
            {"name": "article_id", "data_type": DataType.TEXT},
            {"name": "content", "data_type": DataType.TEXT},
        ]
        self.property_keys = {p["name"] for p in self.properties}
        self.logger = SingletonLoggerSafe.component("WeaviateWriter")
        self.model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
    
    async def __aenter__(self):
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
        
        await self._new_class(self.config["class_name"])
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.client.close()
            await self.logger.ainfo(f"Disconnected from Weaviate at {self.config['host']}:{self.config['http_port']}")
        except Exception as e:
            await self.logger.aerror(f"Failed to disconnect from Weaviate: {e}")
    
    async def _new_class(self, class_name):
        if await self.client.collections.exists(class_name):
            await self.logger.ainfo(f"Class '{class_name}' already exists.")
            return
        
        try:
            await self.logger.ainfo(f"Creating class '{class_name}'")
            await self.client.collections.create(
                    name=class_name,
                    properties = self.properties,
                description="Processed business data stored via message queue"
            )
            await self.logger.ainfo(f"Class '{class_name}' created successfully.")
        except Exception as e:
            await self.logger.aerror(f"Failed to create class '{class_name}': {e}")

    async def store_article(self, article_text):
        try:
            article = ArticlePayload.from_json(article_text)
            collection = self.client.collections.get(self.config["class_name"])
            if article.article_id is not None and article.content is not None:
                embedding = self.model.encode(article.content)
                await collection.data.insert(
                    properties={"article_id": article.article_id, "content": article.content},
                    vector=embedding
                )
                await self.logger.ainfo(f"Article stored successfully: {article}")
        except Exception as e:
            await self.logger.aerror(f"Failed to store article: {e}")
