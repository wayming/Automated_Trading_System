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
from .lru_cache import LRUCache
from .interface import NewsScraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class TwitterScraper(NewsScraper):
    def __init__(self, tweeter, cookies_path="output/x_cookies.json"):
        self.cookies_path = cookies_path
        self.driver = None
        self.article_cache = LRUCache(20)
        self.tweeter = tweeter

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
    
    def _new_login(self) -> bool:
        self.driver = self._start_driver()
        self.driver.get("https://twitter.com/login")

        try:
            # Wait for either login success or 2FA page
            WebDriverWait(self.driver, 60).until(
                lambda d: "home" in d.current_url or 
                         "account/access" in d.current_url or
                         d.find_elements(By.XPATH, "//*[contains(text(), 'Enter your phone')]")
            )
            self._save_cookies()
            print("Login successful!")
            return True
        except Exception as e:
            print(f"Login timeout or failed: {str(e)}")
            raise
    

    def _wait_for_tweets(self):
        """Wait for tweets to load on the page"""
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            return True
        except:
            print("No tweets found within timeout period")
            return False

    
    def _scroll_to_bottom(self, max_tweets):
        """Scroll until the desired number of tweets are loaded"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        tweets_xpath = "//article[@data-testid='tweet']"
        
        while True:
            tweets = self.driver.find_elements(By.XPATH, tweets_xpath)
            if len(tweets) >= max_tweets:
                print(f"Loaded at least {max_tweets} tweets.")
                break

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") > last_height
                )
                last_height = self.driver.execute_script("return document.body.scrollHeight")
            except:
                print("No more content loaded.")
                break


    def login(self) -> bool:
        wait = WebDriverWait(self.driver, 20)

        if os.path.exists(self.cookies_path):
            self.driver = self._start_driver()
            self.driver.get("https://twitter.com/login")
            try:
                self._load_cookies()
                self.driver.refresh()
                self.driver.get("https://twitter.com/home")


                if not self._wait_for_tweets():
                    return False
                print("[+] Logged in using saved cookies.")

                return True
            except Exception:
                print("[!] Failed to login with cookies. Logging in manually.")
                traceback.print_exc()  # shows full traceback
                self.driver.quit()
                return False

        # Start fresh and log in
        return self._new_login()

    def fetch_news(self, limit=5) -> List[str]:
        print("\n" + "="*50)
        print(f"Starting new scan(x.com) at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)

        file_paths = []
        try:
            url = f'https://x.com/{self.tweeter}'
            self.driver.get(url)
            new_articles_found = 0
            if not self._wait_for_tweets():
                return []
            
            self._scroll_to_bottom(limit)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')           
            for tweet in soup.find_all("article", {"data-testid": "tweet"})[:limit]:
                try:
                    # Skip if it's a reply
                    if tweet.find("div", string=re.compile(r"Replying to")):
                        print("Skipping a reply tweet.")
                        continue

                    # Skip if it's a pinned tweet
                    if tweet.find("span", string=re.compile("Pinned Tweet", re.IGNORECASE)):
                        print("Skipping pinned tweet.")
                        continue

                    content = tweet.find("div", {"data-testid": "tweetText"})
                    if not content:
                        print("No tweet text found.")
                        continue

                    content_text = content.get_text()
                    time_element = tweet.find("time")
                    if time_element is None:
                        print("Failed to find the post time of the tweet.")
                        continue

                    print(content_text)
                    print(time_element['datetime'])

                    href = f"https://twitter.com{time_element.parent['href']}"
                    # Skip if article is already in cache
                    if self.article_cache.get(href):
                        print(f"\nSkipping cached article: {href}")
                        continue
                    print(f"\nReading tweet {href}")

                    fname = self._slugify(href)

                    # Save page HTML to file
                    html_path = f"output/{fname}.html"
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(content_text)

                    # Save screenshots
                    # self.driver.save_screenshot(f"output/{fname}.png")

                    # Add to cache
                    self.article_cache.put(href)
                    file_paths.append(html_path)
                    new_articles_found += 1
                except Exception as e:
                    print(f"Failed to read article: {e}")

            if new_articles_found == 0:
                print("\nNo new articles found in this scan")

        except Exception as e:
            print(f"An error occurred when reading new messages: {e}")

        return file_paths

def main():
    scraper = TwitterScraper("elonmusk")
    if not scraper.login():
        return

    while True:
        articles = scraper.fetch_news(limit=5)
        print(articles)
        time.sleep(30)

main()