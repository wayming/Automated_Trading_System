import time
from collections import OrderedDict
import re
from typing import List

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from lru_cache import LRUCache
from interface import NewsScraper


class InvestingScraper(NewsScraper):
    def __init__(self):
        self.driver = None
        self.article_cache = LRUCache(20)

    def _start_driver(self):
        options = uc.ChromeOptions()
        # options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        # options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--start-maximized")

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # options.add_argument("--headless=new")

        self.driver = uc.Chrome(options=options)
        # Avoid loading js which blocks the access
        self.driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*.js"]})
        self.driver.execute_cdp_cmd("Network.enable", {})
        return self.driver
     
    def _slugify(self, text, max_length=100):
        text = re.sub(r'[<>:"/\\|?*\s,\.]', '_', text.strip("'"))
        return text[:max_length]

    def login(self) -> bool:
        self.driver = self._start_driver()
        return True

    def fetch_news(self, limit=5) -> List[str]:
        print("\n" + "="*50)
        print(f"Starting new scan at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)

        file_paths = []

        try:
            url = 'https://au.investing.com/news/headlines'
            self.driver.get(url)

            WebDriverWait(self.driver, 15).until(
                EC.text_to_be_present_in_element(
                    (By.CSS_SELECTOR, "h1.text-xl\\/7.sm\\:text-3xl\\/8.font-bold"), 
                    "Breaking News"
                )
            )
            
            # Extract news (adjust selectors)
            news_items = self.driver.find_elements(By.CSS_SELECTOR, '.inline-block')
            links = [el.get_attribute("href") for el in news_items if el.get_attribute("href")]
            print(links)
            titles = [el.text.strip() for el in news_items]
            print(titles)
            new_articles_found = 0
            for link, title in zip(links[:5], titles[:5]):  #(first 5)
                print(f"标题：{title}\n链接: {link}\n")
                # Skip if article is already in cache
                if self.article_cache.get(link):
                    print(f"\n⏩ Skipping cached article: {link}")
                    continue
                
                print(f"\n🔗 Reading new article: {link}")

                # news contents
                self.driver.get(link)
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.ID, "articleTitle"))
                )

                fname = self._slugify(title)
                print("[+] News read successfully.")
                self.driver.save_screenshot(f"output/{fname}.png")

                # Save page HTML to file
                print(f"\n🔗 Write to file: {fname}")
                with open(f"output/{fname}.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                print(f"[+] Saved full HTML to output/{fname}.html.")
                file_paths.append(f"output/{fname}.html")

                # Add to cache
                self.article_cache.put(url)
                new_articles_found += 1
                
            if new_articles_found == 0:
                print("\nℹ️ No new articles found in this scan")
            
        except Exception as e:
            print(f"⚠️ An error occurred: {str(e)}")

        return file_paths
    

def main():
    scraper = InvestingScraper()
    if not scraper.login():
        return

    articles = scraper.fetch_news(limit=5)
    print(articles)

main()
