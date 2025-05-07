import os
import time
import re
import pickle
import traceback
from typing import List

from selenium.webdriver.common.by  import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support    import expected_conditions as EC

import undetected_chromedriver as uc
from lru_cache import LRUCache
from interface import NewsScraper


class TradingViewScraper(NewsScraper):
    def __init__(self, username: str, password: str, cookies_path="output/cookies.pkl"):
        self.username = username
        self.password = password
        self.cookies_path = cookies_path
        self.driver = None
        self.cache = LRUCache(20)

    def _start_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless=new")
        return uc.Chrome(options=options)

    def _save_cookies(self):
        with open(self.cookies_path, "wb") as file:
            pickle.dump(self.driver.get_cookies(), file)

    def _load_cookies(self):
        with open(self.cookies_path, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                self.driver.add_cookie(cookie)

    def _slugify(self, text, max_length=100):
        text = re.sub(r'[<>:"/\\|?*\s,\.]', '_', text.strip("'"))
        return text[:max_length]
    
    def login(self) -> bool:
        self.driver = self._start_driver()
        wait = WebDriverWait(self.driver, 20)

        self.driver.get("https://www.tradingview.com/#signin")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Email']")))
            self.driver.find_element(By.XPATH, "//span[text()='Email']").click()

            wait.until(EC.presence_of_element_located((By.NAME, "id_username")))
            self.driver.find_element(By.NAME, "id_username").send_keys(self.username)
            self.driver.find_element(By.NAME, "id_password").send_keys(self.password + "\n")

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))
            self._save_cookies()
            print("[+] Logged in successfully.")
            return True
        except Exception as e:
            print("[!] Login failed with exception:")
            traceback.print_exc()  # shows full traceback
            self.driver.quit()
            return False


    def fetch_news(self, limit=5) -> List[str]:
        self.driver.get("https://www.tradingview.com/news-flow/")
        time.sleep(5)

        news_elements = self.driver.find_elements(By.CSS_SELECTOR, ".card-HY0D0owe")
        links = [el.get_attribute("href") for el in news_elements if el.get_attribute("href")]
        titles = [el.find_element(By.CSS_SELECTOR, ".title-HY0D0owe").text for el in news_elements]

        saved_files = []

        for url, title in zip(links[:limit], titles[:limit]):
            if self.cache.get(url):
                continue

            self.driver.get(url)
            time.sleep(5)
            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".body-KX2tCBZq")))
                fname = self._slugify(title)
                html_path = f"output/{fname}.html"

                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)

                self.driver.save_screenshot(f"output/{fname}.png")
                self.cache.put(url)
                saved_files.append(html_path)
            except Exception as e:
                print(f"[!] Failed to read article: {e}")

        return saved_files

def main():
    USERNAME = os.getenv("TRADE_VIEW_USER")
    PASSWORD = os.getenv("TRADE_VIEW_PASS")

    scraper = TradingViewScraper(USERNAME, PASSWORD)
    if not scraper.login():
        return

    articles = scraper.fetch_news(limit=5)
    print(articles)

# main()