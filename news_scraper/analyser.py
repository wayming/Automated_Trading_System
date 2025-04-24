import os
import requests
import json
import re
from bs4 import BeautifulSoup

# === CONFIG ===
API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/v1/chat/completions"  # or the correct endpoint

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# === FUNCTIONS ===

def extract_article_info(html):
    soup = BeautifulSoup(html, 'html.parser')

    title_tag = soup.find('h1', class_='title-KX2tCBZq')
    title = title_tag.text.strip() if title_tag else "Title not found"

    content_div = soup.find('div', class_='body-KX2tCBZq')
    if content_div:
        paragraphs = content_div.find_all('p')
        content = "\n".join(p.get_text(strip=True) for p in paragraphs)
    else:
        content = "Content not found"

    return {
        "title": title,
        "content": content
    }

def send_to_deepseek(prompt_text):
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.7
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Request failed: {response.status_code} - {response.text}")

def extract_response_struct(full_response):
    # Extract the JSON section between triple backticks
    match = re.search(r'```[\s\n]*({.*?})[\s\n]*```', full_response, re.DOTALL)
    if match:
        json_text = match.group(1)
        try:
            # Convert to Python dictionary
            extracted_data = json.loads(json_text)
            print("Serialized JSON object:")
            print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError as e:
            print("Failed to parse JSON:", e)
    else:
        print("No JSON block found in the response.")

def run_pipeline(html_path, prompt_path):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    article = extract_article_info(html)

    with open(prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    full_prompt = (
        f"{base_prompt}\n\n"
        f"---\n\n"
        f"Title: {article['title']}\n\n"
        f"Content:\n{article['content']}"
    )

    print(full_prompt)
    response = send_to_deepseek(full_prompt)
    return response

# === RUN SCRIPT ===
if __name__ == "__main__":
    # result = run_pipeline("output/https__www.tradingview.com_news_mtnewswires.com20250423G24949880_.html", "prompt.txt")
    # print("DeepSeek Response:\n")
    # print(result)