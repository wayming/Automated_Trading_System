from abc import ABC, abstractmethod
from typing import List

class NewsScraper(ABC):
    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def fetch_news(self, limit: int) -> List[str]:
        pass


class NewsAnalyser(ABC):
    @abstractmethod
    def analyse(self, html_text: str) -> dict:
        pass
