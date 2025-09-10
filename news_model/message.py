from dataclasses import dataclass, field
import uuid
import json
from datetime import datetime

@dataclass
class ArticlePayload:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    time: str = field(default_factory=lambda: datetime.now().isoformat())
    title: str = ""
    content: str = ""
    analysis: dict = None
    error: str = ""
    
    def to_json(self):
        return json.dumps(self.__dict__)
    
    @classmethod
    def from_json(cls, json_str: str):
        return cls(**json.loads(json_str))
        

