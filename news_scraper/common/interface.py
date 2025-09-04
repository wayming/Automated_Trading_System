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

class ScraperFactory(ABC):
    @abstractmethod
    def create_scraper(self) -> NewsScraper:
        pass