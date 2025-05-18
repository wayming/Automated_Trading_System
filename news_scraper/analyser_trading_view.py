import os
import json
import re
import requests
import pika

from bs4                import BeautifulSoup
from requests.adapters  import HTTPAdapter
from urllib3.util.retry import Retry
from .interface          import NewsAnalyser


class TradingViewAnalyser(NewsAnalyser):
    def __init__(self, api_key: str, prompt_path: str):
        self.api_key = api_key
        self.prompt_path = prompt_path
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _extract_article(self, html_text):
        soup = BeautifulSoup(html_text, 'html.parser')

        title = soup.find('h1', class_='title-KX2tCBZq')
        content = soup.find('div', class_='body-KX2tCBZq')

        return {
            "title": title.text.strip() if title else "No Title",
            "content": "\n".join(p.get_text(strip=True) for p in content.find_all('p')) if content else "No Content"
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
        with open("output/investing_analyser.log", "a", encoding="utf-8") as f:
            f.write("\n\n" + ">"*80 + "\n")
            f.write("Full Response:\n")
            f.write(response)
            # f.write(json.dumps(result, ensure_ascii=False))
            f.write("\n" + ">"*80 + "\n\n")
        return result


def consumer_callback(ch, method, properties, body):
    article_text = body.decode()
    print("[Consumer] Received HTML content.")

    this_dir = Path(__file__).parent
    analyser = TradingViewAnalyser(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        prompt_path=this_dir/"prompt.txt"
    )

    result = analyser.analyse(article_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    print("[Consumer] Connecting to RabbitMQ...")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='tv_articles')
    channel.basic_consume(queue='tv_articles', on_message_callback=consumer_callback, auto_ack=True)
    print("[Consumer] Waiting for messages...")
    channel.start_consuming()


if __name__ == "__main__":
    main()