import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class TwitterScraper:
    def __init__(self, username, headless=True):
        self.username = username
        self.cookie_file = f"twitter_cookies_{username}.json"
        self.url = f"https://twitter.com/{username}"
        self.driver = self._init_driver(headless)
        
    def _init_driver(self, headless):
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=en-US")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        return driver
    
    def _save_cookies(self):
        cookies = self.driver.get_cookies()
        with open(self.cookie_file, 'w') as f:
            json.dump(cookies, f)
        print("Cookies saved successfully")
    
    def _load_cookies(self):
        if not os.path.exists(self.cookie_file):
            return False
            
        with open(self.cookie_file, 'r') as f:
            cookies = json.load(f)
            
        self.driver.get("https://twitter.com")
        for cookie in cookies:
            if 'domain' in cookie and cookie['domain'].startswith('.'):
                cookie['domain'] = cookie['domain'][1:]
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                print(f"Error adding cookie: {e}")
        return True
    
    def login_manually(self):
        print("Please log in to Twitter manually...")
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
    
    def _scroll_to_bottom(self):
        """Scroll to bottom with dynamic wait"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") > last_height
                )
                last_height = self.driver.execute_script("return document.body.scrollHeight")
            except:
                break  # No more content loaded
    
    def scrape_tweets(self, max_tweets=10):
        if not self._load_cookies():
            self.login_manually()
        
        self.driver.get(self.url)
        
        if not self._wait_for_tweets():
            return []
        
        self._scroll_to_bottom()
        
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        tweets = []
        
        for tweet in soup.find_all("article", {"data-testid": "tweet"})[:max_tweets]:
            try:
                content = tweet.find("div", {"data-testid": "tweetText"}).get_text()
                time_element = tweet.find("time")
                
                tweets.append({
                    'content': content,
                    'timestamp': time_element['datetime'] if time_element else None,
                    'url': f"https://twitter.com{time_element.parent['href']}" if time_element else None
                })
            except Exception as e:
                print(f"Error parsing tweet: {str(e)}")
        
        return tweets
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    scraper = TwitterScraper("elonmusk", headless=False)
    
    try:
        tweets = scraper.scrape_tweets(max_tweets=5)
        print(f"\nScraped {len(tweets)} tweets:")
        for i, tweet in enumerate(tweets, 1):
            print(f"\n{i}. [{tweet['timestamp']}]")
            print(tweet['content'])
            print(f"URL: {tweet['url']}")
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    finally:
        scraper.close()