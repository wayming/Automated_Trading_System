import os
import json
import re
import requests

from bs4                import BeautifulSoup
from requests.adapters  import HTTPAdapter
from urllib3.util.retry import Retry
from .interface          import NewsAnalyser


class InvestingAnalyser(NewsAnalyser):
    def __init__(self, api_key: str, prompt_path: str):
        self.api_key = api_key
        self.prompt_path = prompt_path
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _extract_article(self, html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        title_tag = soup.find('h1', id='articleTitle')
        title = title_tag.get_text(strip=True) if title_tag else ''

        article = soup.find('div', id='article')
        content = []

        if article is not None:
            for tag in article.find_all(['p', 'div'], recursive=True):
                if tag.name == 'div' and tag.get('id') == 'article-newsletter-hook':
                    break  # End of content
                if tag.name == 'p':
                    content.append(tag.get_text(strip=True))

        # for para in content:
        #     print(para)

        return {
            "title": title if title else "No Title",
            "content": "\n".join(content) if content else "No Content"
        }


    def _send_to_llm(self, prompt_text):
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.7
        }

        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))

        resp = session.post(self.api_url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']

    def _extract_structured_response(self, response_text):
        pattern = r'^-{3,}\s*\n(.*?)\n-{3,}$'
        match = re.search(pattern, response_text, re.DOTALL | re.MULTILINE)
        if not match:
            print(f"No structure resposne found from llm response:\n{response_text}")
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON struct.\n{match.group(1)}\nError: {e}")
            return None

    def analyse(self, html_path: str) -> dict:

        article = self._extract_article(html_path)
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            base_prompt = f.read()

        prompt = f"{base_prompt}\n\n---\n\nTitle: {article['title']}\n\nContent:\n{article['content']}"
        response = self._send_to_llm(prompt)

        result = self._extract_structured_response(response)
        with open(html_path.replace(".html", ".resp"), "w", encoding="utf-8") as f:
            f.write(response)
        return result


def main():
    API_KEY = os.getenv("DEEPSEEK_API_KEY")

    analyser = InvestingAnalyser(API_KEY, "prompt.txt")

    article_path = "output/Walt_Disney_shares_gain_8%_as_earnings__outlook_beat_estimates.html"
    result = analyser.analyse(article_path)
    print(f"\n✅ Analysis result for {article_path}:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

# main()