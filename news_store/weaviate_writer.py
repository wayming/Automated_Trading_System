import weaviate
from weaviate.connect import ConnectionParams, ProtocolParams
from weaviate.collections.classes.config import DataType
from typing import TypedDict
from news_model.processed_article import ProcessedArticle
from news_model.article_message import ArticlePayload

class WeaviateConfig(TypedDict):
    host: str
    http_port: str
    grpc_port: str
    class_name: str

class WeaviateClient:
    def __init__(self, config: WeaviateConfig):
        self.config = config
    
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
            SingletonLoggerSafe.info(f"Connected to Weaviate at {config['host']}:{config['http_port']}")
        except Exception as e:
            raise Exception(f"Failed to connect to Weaviate: {e}")
        
        self._new_class(config["class_name"])
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.client.close()
            SingletonLoggerSafe.info(f"Disconnected from Weaviate at {self.config['host']}:{self.config['http_port']}")
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to disconnect from Weaviate: {e}")
    
    async def _new_class(self, class_name):
        if await self.client.collections.exists(class_name):
            SingletonLoggerSafe.info(f"Class '{class_name}' already exists.")
            return
        
        try:
            SingletonLoggerSafe.info(f"Creating class '{class_name}'")
            await self.client.collections.create(
                    name=class_name,
                    properties = [
                    {"name": "id", "data_type": DataType.TEXT},
                    {"name": "time", "data_type": DataType.DATE},
                    {"name": "title", "data_type": DataType.TEXT},
                    {"name": "content", "data_type": DataType.TEXT},
                    {"name": "analysis", "data_type": DataType.TEXT},
                    {"name": "error", "data_type": DataType.TEXT},
                ],
                description="Processed business data stored via message queue"
            )
            SingletonLoggerSafe.info(f"Class '{class_name}' created successfully.")
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to create class '{class_name}': {e}")

    async def store_article(self, article_text):
        try:
            article = ArticlePayload.from_json(article_text)
            collection = await self.client.collections.get(self.config["class_name"])
            await collection.data.insert(article.__dict__)
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to store article: {e}")
