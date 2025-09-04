from abc import ABC, abstractmethod
from typing import List

class NewsAnalyser(ABC):
    @abstractmethod
    def analyse(self, html_text: str) -> dict:
        pass
class NewsScraper(ABC):
    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def fetch_news(self, limit: int) -> List[str]:
        pass

class ScraperContext(ABC):
    @abstractmethod
    def __enter__(self):
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
