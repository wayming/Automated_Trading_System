import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
import requests
import time
from collections import OrderedDict
import re
import sys
import os

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> bool:
        if key not in self.cache:
            return False
        self.cache.move_to_end(key)
        return True

    def put(self, key: str) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)
        self.cache[key] = True

# Initialize LRU cache with capacity of 20
article_cache = LRUCache(20)


def slugify_filename(text, max_length=100):
    text = text.strip("'")
    # Replace special characters with underscores
    text = re.sub(r'[<>:"/\\|?*\s,\.]', '_', text)
    # Trim to max length
    return text[:max_length]

def read_message(driver):
    print("\n" + "="*50)
    print(f"Starting new scan at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    file_paths = []

    try:
        # 获取新闻页面内容
        url = 'https://au.investing.com/news/headlines'

        driver.get(url)
        time.sleep(5)  # wait for JS content to load

        # Extract news (adjust selectors)
        news_items =driver.find_elements("css selector", ".text_sm")
        print(news_items)
        return file_paths
    
        # 提取标题和链接
        titles = [el.get_text(strip=True) for el in news_items]
        links = ['https://au.investing.com' + el['href'] for el in news_items if el.has_attr('href')]

        new_articles_found = 0

        print(list(zip(titles, links)))
        new_articles_found = 0
        for link, title in zip(links[:5], titles[:5]):  #(first 5)
            print(f"标题：{title}\n链接：https://au.investing.com{link}\n")
            # Skip if article is already in cache
            if article_cache.get(link):
                print(f"\n⏩ Skipping cached article: {link}")
                continue
            
            print(f"\n🔗 Reading new article: {link}")

            # 获取新闻详情
            article_response = requests.get(link)
            article_soup = BeautifulSoup(article_response.content, 'html.parser')
            content = article_soup.find('div', class_='article_WYSIWYG__O0uhw').get_text(strip=True)
            print(f"内容：{content[:200]}...")  # 仅显示前200个字符
            print('-' * 80)

            fname = slugify_filename(title)
            print(f"\n🔗 Write to file: {fname}")
            with open(f"output/{fname}.html", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] Saved full HTML to output/{fname}.html.")
            file_paths.append(f"output/{fname}.html")

            # Add to cache
            article_cache.put(url)
            new_articles_found += 1
            
            if new_articles_found == 0:
                print("\nℹ️ No new articles found in this scan")
        
    except Exception as e:
        print(f"⚠️ An error occurred: {str(e)}")

    return file_paths

def start_firefox_driver(headless=False):
    options = Options()

    # Enable headless mode if needed
    if headless:
        options.headless = True

    # Set custom user-agent
    options.set_preference(
        "general.useragent.override",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0"
    )

    # Try to reduce automation fingerprint
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)

    # Explicit binary location (only needed if not in standard path)
    options.binary_location = "/usr/bin/firefox"

    # Start the driver
    driver = webdriver.Firefox(options=options)
    return driver


# def start_driver(headless=False):
#     options = uc.ChromeOptions()

#     # Try to avoid detection
#     options.add_argument("--disable-blink-features=AutomationControlled")
#     options.add_argument("--disable-infobars")
#     options.add_argument("--disable-extensions")
#     options.add_argument("--start-maximized")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")

#     # Enable headless mode if requested
#     if headless:
#         options.headless = True

#     # Start the browser
#     driver = uc.Chrome(options=options)
#     return driver


def start_driver():
    options = Options()
    #options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)
    return driver

def main():

    # Start WebDriver
    driver = start_driver()

    # Run the function in a loop with 3-second delay
    while True:
        news = read_message(driver)
        for n in news:
            print(n)
        print("\n" + "="*50)
        print(f"Cache size: {len(article_cache.cache)}/20 | Waiting 3 seconds before next scan...")
        print("="*50 + "\n")
        break
        time.sleep(3)

main()