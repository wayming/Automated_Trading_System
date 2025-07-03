import weaviate
from weaviate.connect import ConnectionParams, ProtocolParams
from weaviate.collections.classes.config import DataType
class WeaviateClient:
    def __init__(self, wv_config):
        print(wv_config)
        self.client = weaviate.WeaviateClient(
            connection_params=ConnectionParams.from_params(
                http_host=wv_config["host"],
                http_port=wv_config["http_port"],
                http_secure=False,
                grpc_host=wv_config['host'],
                grpc_port=wv_config["grpc_port"],
                grpc_secure=False,
            )
        )

        self.client.connect()
        print(f"[Weaviate] Connected to Weaviate at {wv_config['host']}:{wv_config['http_port']}")
        self.class_name = wv_config["class_name"]
        self._new_class()
        
    def _new_class(self):
        if not self.client.collections.exists(self.class_name):
            print(f"[Weaviate] Creating class '{self.class_name}'")
            self.client.collections.create(
                name=self.class_name,
                properties = [
                    {"name": "uuid", "data_type": DataType.TEXT},
                    {"name": "title", "data_type": DataType.TEXT},
                    {"name": "content", "data_type": DataType.TEXT},
                    {"name": "timestamp", "data_type": DataType.DATE},
                    {"name": "analysis_results", "data_type": DataType.TEXT},
                ],
                description="Processed business data stored via message queue"
            )
        else:
            print(f"[Weaviate] Class '{self.class_name}' already exists.")


    def store_news(self, news_data):
        self.client.data_object.create(
            data_object=news_data,
            class_name=self.class_name
        )