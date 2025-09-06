from dataclasses import dataclass
import uuid
import json

@dataclass
class ArticleMessage:
    title: str = ""
    content: str = ""
    response_struct: dict = None
    response_raw: str = ""

    # private field
    _message_id: str = str(uuid.uuid4())

    @property
    def message_id(self):
        return self._message_id
    
    def to_json(self):
        return json.dumps(self.__dict__)
    
    @classmethod
    def from_json(cls, json_str: str):
        return cls(**json.loads(json_str))
        

