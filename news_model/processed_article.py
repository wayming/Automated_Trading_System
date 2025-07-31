from dataclasses import dataclass

@dataclass
class ProcessedArticle:
    uuid: str
    title: str
    content: str
    timestamp: str
    analysis_results: str
