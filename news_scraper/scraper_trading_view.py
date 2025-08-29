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
from selenium.webdriver import Remote as RemoteWebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

import undetected_chromedriver as uc

from prometheus_client import start_http_server, Counter
from prometheus_client import Gauge
from .lru_cache import LRUCache
from .interface import NewsScraper
import pika

QUEUE_TV_ARTICLES = "tv_articles"

SCRAPE_COUNT = Counter("scraper_runs_total", "Number of scraper runs")
SCRAPE_ERRORS = Counter("scraper_errors_total", "Number of errors during scraping")
LAST_SCRAPE = Gauge("scraper_last_scrape_timestamp", "Last scrape time (unix)")

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
        # options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")

        hub_url = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444/wd/hub")
        driver = RemoteWebDriver(
            command_executor=hub_url,
            options=options
        )
        return driver

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
        wait = WebDriverWait(self.driver, 200)

        self.driver.get("https://www.tradingview.com/#signin")

        try:
            print("Waiting for 'Email' button...")
            email_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='Email']"))
            )
            email_button.click()
            print("Clicked 'Email' button.")

            print("Waiting for username field...")
            wait.until(EC.presence_of_element_located((By.ID, "id_username")))

            self.driver.find_element(By.ID, "id_username").send_keys(self.username)
            self.driver.find_element(By.ID, "id_password").send_keys(self.password)

            # Wait robot screening
            # Maually resolve the robot screening and then click the "Sign in" button.
            # Somehow the program click the "Sign in" button causes login failure.
            time.sleep(40)

            # print("Waiting for sign-in button...")
            # sign_in_button = wait.until(
            #     EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Sign in']]"))
            # )
            # sign_in_button.click()

            print("Waiting for dashboard...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))

            self._save_cookies()
            print("[+] Logged in successfully.")
            return True

        except Exception as e:
            print("[!] Login failed with exception:")
            traceback.print_exc()
            self.driver.quit()
            return False
        
    def login(self) -> bool:
        wait = WebDriverWait(self.driver, 20)

        if os.path.exists(self.cookies_path):
            self.driver = self._start_driver()
            self.driver.get("https://www.tradingview.com/news-flow/")
            try:
                self._load_cookies()
                self.driver.refresh()
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".filtersBar-YXVzia8q"))
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
                EC.presence_of_element_located((By.CLASS_NAME, "card-DmjQR0Aa"))
            )

            new_items = self.driver.find_elements(By.CSS_SELECTOR, ".card-DmjQR0Aa")
            links = [el.get_attribute("href") for el in new_items if el.get_attribute("href")]
            titles = [el.find_element(By.CSS_SELECTOR, ".title-e7vDzPX4").text for el in new_items]
            
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

            LAST_SCRAPE.set_to_current_time()
        except Exception as e:
            self.driver.save_screenshot(f"output/investing_error.png")
            print(f"An error occurred when reading new messages: {e}")
            SCRAPE_ERRORS.inc()
        return file_paths

def rabbit_mq_connect() -> pika.BlockingConnection:
    while True:
        try:
            print("[Scraper_Trading_View] Connecting to RabbitMQ...")
            host = os.getenv("RABBITMQ_HOST", "rabbitmq")
            username = os.getenv("RABBITMQ_USER", "admin")
            password = os.getenv("RABBITMQ_PASS", "password")
            rabbit_connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=host, credentials=pika.PlainCredentials(username, password))
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

    start_http_server(8000)

    scraper = scraper = TradingViewScraper(
            username=USERNAME,
            password=PASSWORD,
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
        SCRAPE_COUNT.inc()
        time.sleep(10)

if __name__ == "__main__":
    main()