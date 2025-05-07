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

        WebDriverWait(driver, 15).until(
            EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, "h1.text-xl\\/7.sm\\:text-3xl\\/8.font-bold"), 
                "Breaking News"
            )
        )
        
        # Extract news (adjust selectors)
        news_items = driver.find_elements(By.CSS_SELECTOR, '.inline-block')
        links = [el.get_attribute("href") for el in news_items if el.get_attribute("href")]
        print(links)
        titles = [el.text.strip() for el in news_items]
        print(titles)
        new_articles_found = 0
        for link, title in zip(links[:5], titles[:5]):  #(first 5)
            print(f"标题：{title}\n链接: {link}\n")
            # Skip if article is already in cache
            if article_cache.get(link):
                print(f"\n⏩ Skipping cached article: {link}")
                continue
            
            print(f"\n🔗 Reading new article: {link}")

            # 获取新闻详情
            # article_response = requests.get(link)
            # article_soup = BeautifulSoup(article_response.content, 'html.parser')
            driver.get(link)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "articleTitle"))
            )

            fname = slugify_filename(title)
            print("[+] News read successfully.")
            driver.save_screenshot(f"output/{fname}.png")

            # 8. Save page HTML to file
            print(f"\n🔗 Write to file: {fname}")
            with open(f"output/{fname}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
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
    
def start_driver():
    options = Options()
    #options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # options.add_argument("--headless=new")

    driver = uc.Chrome(options=options)
    # Avoid loading js which blocks the access
    driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*.js"]})
    driver.execute_cdp_cmd("Network.enable", {})
    return driver

def main():
    print(uc.__version__)
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
        time.sleep(3)

main()
