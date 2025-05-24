import os
import time
import re
import pickle
import traceback
import argparse
from typing import List

from selenium.webdriver.common.by  import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support    import expected_conditions as EC
import undetected_chromedriver as uc

from .lru_cache import LRUCache
from .interface import NewsScraper
import pika

QUEUE_TV_ARTICLES = "tv_articles"
class TradingViewScraper(NewsScraper):
    def __init__(
            self,
            username: str,
            password: str,
            cookies_path="output/trading_view_cookies.pkl",
            queue_conn: pika.BlockingConnection = None,
            queue_name = QUEUE_TV_ARTICLES):
        self.username = username
        self.password = password
        self.cookies_path = cookies_path
        self.driver = None
        self.article_cache = LRUCache(20)
        self.queue_name = queue_name
        self.output_dir = "output/trading_view"
        os.makedirs(self.output_dir, exist_ok=True)

        if queue_conn != None:
            self.queue_channel = queue_conn.channel()
            self.queue_channel.queue_declare(queue=queue_name, durable=True)

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
        wait = WebDriverWait(self.driver, 20)

        self.driver.get("https://www.tradingview.com/#signin")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Email']")))
            self.driver.find_element(By.XPATH, "//span[text()='Email']").click()

            wait.until(EC.presence_of_element_located((By.NAME, "id_username")))
            self.driver.find_element(By.NAME, "id_username").send_keys(self.username)
            self.driver.find_element(By.NAME, "id_password").send_keys(self.password + "\n")

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))
            input("Enter to continue")
            self._save_cookies()
            print("[+] Logged in successfully.")
            return True
        except Exception as e:
            print("[!] Login failed with exception:")
            traceback.print_exc()  # shows full traceback
            self.driver.quit()
            return False

    def login(self) -> bool:
        wait = WebDriverWait(self.driver, 20)

        if os.path.exists(self.cookies_path):
            self.driver = self._start_driver()
            self.driver.get("https://www.tradingview.com")
            try:
                self._load_cookies()
                self.driver.refresh()

                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts"))
                )
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
        print(f"Starting new scan(www.tradingview.com) at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)

        file_paths = []
        try:
            url = 'https://www.tradingview.com/news-flow/'
            self.driver.get(url)

            # wait page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "card-HY0D0owe"))
            )

            new_items = self.driver.find_elements(By.CSS_SELECTOR, ".card-HY0D0owe")
            links = [el.get_attribute("href") for el in new_items if el.get_attribute("href")]
            titles = [el.find_element(By.CSS_SELECTOR, ".title-HY0D0owe").text for el in new_items]
            
            new_articles_found = 0
            for link, title in zip(links[:limit], titles[:limit]):
                # Skip if article is already in cache
                if self.article_cache.get(link):
                    print(f"\nSkipping cached article: {link}")
                    continue

                print(f"\nReading new article.")
                print(f"title: {title}\nlink: {link}\n")

                try:
                    self.driver.get(link)
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".body-KX2tCBZq")))

                    # Save page HTML to file
                    fname = self._slugify(title)
                    html_path = f"{self.output_dir}/{fname}.html"
                    html_content = self.driver.page_source
                    
                    # Save to file 
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print(f"Saved HTML to {html_path}")
                    file_paths.append(html_path)
                    
                    if self.queue_channel != None:
                        self.queue_channel.basic_publish(
                            exchange='',
                            routing_key=self.queue_name,
                            body=html_content.encode('utf-8')
                        )
                        print(f"Sent article to queue: {fname}")
                    else:
                        print(f"No queue")

                    # Add to cache
                    self.article_cache.put(link)
                    file_paths.append(html_path)
                    new_articles_found += 1
                except Exception as e:
                    print(f"Failed to read article: {e}")

            if new_articles_found == 0:
                print("\nNo new articles found in this scan")

        except Exception as e:
            self.driver.save_screenshot(f"output/investing_error.png")
            print(f"An error occurred when reading new messages: {e}")

        return file_paths

def rabbit_mq_connect() -> pika.BlockingConnection:
    while True:
        try:
            print("[Scraper_Trading_View] Connecting to RabbitMQ...")
            rabbit_connection = pika.BlockingConnection(
                pika.ConnectionParameters(host="rabbitmq")
            )
            print("[Scraper_Trading_View] Connected to RabbitMQ.")
            return rabbit_connection
        except pika.exceptions.AMQPConnectionError:
            print("[Scraper_Trading_View] Waiting for RabbitMQ...")
            time.sleep(2)

def main():
    parser = argparse.ArgumentParser(description="TradingView News Scraper")
    parser.add_argument("--login", action="store_true", help="Only perform login and exit")
    args = parser.parse_args()

    USERNAME = os.getenv("TRADE_VIEW_USER")
    PASSWORD = os.getenv("TRADE_VIEW_PASS")
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials. Set TRADE_VIEW_USER and TRADE_VIEW_PASS in your environment.")
        return
    
    mq_conn = None
    if not args.login:
        mq_conn = rabbit_mq_connect()

    scraper = scraper = TradingViewScraper(
            username="myuser",
            password="mypass",
            queue_conn=mq_conn,
            queue_name=QUEUE_TV_ARTICLES
    )
    if not scraper.login():
        print("❌ Login failed.")
        return

    if args.login:
        print("✅ Login successful. Exiting as requested.")
        return

    while True:
        if mq_conn.is_open:
            mq_conn.process_data_events() #Heartbeat
        else:
            print("❌ RabbitMQ connection dropped.")
            break

        articles = scraper.fetch_news(limit=5)
        print(articles)
        time.sleep(10)

if __name__ == "__main__":
    main()