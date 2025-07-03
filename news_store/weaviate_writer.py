import weaviate
from weaviate.connect import ConnectionParams, ProtocolParams
class WeaviateClient:
    def __init__(self, wv_url, wv_class_name):

        self.client = weaviate.WeaviateClient(
            connection_params=ConnectionParams.from_params(
                http_host="weaviate",
                http_port=50054,
                http_secure=False,
                grpc_host="weaviate",
                grpc_port=50052,
                grpc_secure=False,
            )
        )
        self.class_name = wv_class_name
        self._new_class()
        
    def _new_class(self):
        if not self.client.schema.contains(self.class_name):
            print(f"[Weaviate] Creating class '{self.class_name}'")
            class_obj = {
                "class": self.class_name,
                "description": "Processed business data stored via message queue",
                "properties": [
                    {"name": "uuid", "dataType": ["text"]},
                    {"name": "title", "dataType": ["text"]},
                    {"name": "content", "dataType": ["text"]},
                    {"name": "timestamp", "dataType": ["date"]},
                    {"name": "analysis_results", "dataType": ["text"]}
                ]
            }
            self.client.schema.create_class(class_obj)
        else:
            print(f"[Weaviate] Class '{self.class_name}' already exists.")

    def store_news(self, news_data):
        self.client.data_object.create(
            data_object=news_data,
            class_name=self.class_name
        )