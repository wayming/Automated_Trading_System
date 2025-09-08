from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from pathlib import Path

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
    _prompt_path: Path = None

    @property
    def model_name(self):
        return self._model_name

    @property
    def base_url(self):
        return self._base_url
    
    @property
    def api_url(self):
        return self._api_url

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
        if self._prompt_path is None:
            self._prompt_path = Path(__file__).parent / "prompt.txt"
        if not os.path.exists(self._prompt_path):
            raise ValueError(f"Prompt file not found at: {self._prompt_path}")
        return self._prompt_path