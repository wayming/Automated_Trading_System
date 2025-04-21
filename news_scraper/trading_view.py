from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import time

# Set up Selenium headless browser
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 1. Visit TradingView News Flow
driver.get("https://www.tradingview.com/news-flow/")
time.sleep(5)  # wait for JS content to load

# 2. Get all news <a> links
news_elements = driver.find_elements("css selector", "a.card-HY0D0owe")
links = [el.get_attribute("href") for el in news_elements if el.get_attribute("href")]

driver.quit()

# 3. Use BeautifulSoup to extract each article's content
headers = {"User-Agent": "Mozilla/5.0"}


for url in links[:5]:  # limit for demo (first 5)
    print(f"\n🔗 Reading: {url}")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # 1. Extract title from the <h1> tag
    title = soup.find("h1")
    print("📌 Title:", title.text.strip() if title else "N/A")

    # 2. Extract main article content under <div class="body-KX2tCBZq">
    body_div = soup.find("div", class_="body-KX2tCBZq")

    if body_div:
        paragraphs = body_div.find_all("p")
        print("📝 Content:")
        # Extract all text from the <p> tags within the body section
        for p in paragraphs:
            print("-", p.get_text(strip=True))
    else:
        print("⚠️ Article body not found.")
