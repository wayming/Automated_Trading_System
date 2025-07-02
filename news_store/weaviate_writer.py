import weaviate

class WeaviateClient:
    def __init__(self, url, class_name):
        self.client = weaviate.Client(url=url)
        self.class_name = class_name

    def store_news(self, news_data):
        self.client.data_object.create(
            data_object=news_data,
            class_name=self.class_name
        )