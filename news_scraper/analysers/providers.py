from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

class LLMProvider(ABC):

    @property
    @abstractmethod
    def model_name(self):
        pass
    
    @property
    @abstractmethod
    def base_url(self):
        pass
    
    @property
    @abstractmethod
    def api_url(self):
        pass
    
    @property
    @abstractmethod
    def api_key(self):
        pass
    
    @property
    @abstractmethod
    def headers(self):
        pass

    @property
    @abstractmethod
    def prompt_path(self):
        pass

@dataclass
class DeepSeekProvider(LLMProvider):
    _model_name: str = "deepseek-chat"
    _base_url: str = "https://api.deepseek.com"
    _api_url: str = "https://api.deepseek.com/v1/chat/completions"
    _prompt_path: str = ""

    @property
    def model_name(self):
        return self._model_name

    @property
    def base_url(self):
        return self._base_url
    
    @property
    def api_url(self):
        return self.api_url

    @property
    def api_key(self):
        if os.getenv("DEEPSEEK_API_KEY") is None or os.getenv("DEEPSEEK_API_KEY") == "":
            raise ValueError("DEEPSEEK_API_KEY is not set")
        return os.getenv("DEEPSEEK_API_KEY")

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @property
    def prompt_path(self):
        this_dir = Path(__file__).parent
        if not os.path.exists(this_dir / "prompt.txt"):
            raise ValueError("Prompt file not found")
        return this_dir / "prompt.txt"