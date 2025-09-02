import os
import time
import re
import pickle
import traceback
import argparse
import aio_pika
import undetected_chromedriver as uc
import asyncio
import threading
import signal
import json
from typing import List, Optional
from bs4 import BeautifulSoup

from selenium.webdriver.common.by  import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support    import expected_conditions as EC
from selenium.webdriver import Remote as RemoteWebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from prometheus_client import start_http_server, Counter
from prometheus_client import Gauge
from .lru_cache import LRUCache
from .interface import NewsScraper
from .common import get_logger, cached_fetcher, new_mq_channel, log_section

QUEUE_TV_ARTICLES = "tv_articles"

SCRAPE_COUNT = Counter("scraper_runs_total", "Number of scraper runs")
SCRAPE_ERRORS = Counter("scraper_errors_total", "Number of errors during scraping")
LAST_SCRAPE = Gauge("scraper_last_scrape_timestamp", "Last scrape time (unix)")

logger = get_logger("output/scraper_trading_view.log")

class TradingViewScraper(NewsScraper):
    def __init__(
            self,
            username: str,
            password: str,
            cookies_path="output/trading_view_cookies.pkl"):
        self.username = username
        self.password = password
        self.cookies_path = cookies_path
        self.driver = None
        self.article_cache = LRUCache(20)
        self.output_dir = "output/trading_view"
        os.makedirs(self.output_dir, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

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
                logger.info("Logged in using saved cookies.")

                return True
            except Exception:
                logger.error("Failed to login with cookies. Logging in manually.")
                traceback.print_exc()  # shows full traceback
                self.driver.quit()
                return False

        # Start fresh and log in
        return self._new_login()

    def fetch_news(self, limit=5) -> List[dict]:
        log_section(logger, "Starting new scan(www.tradingview.com)")
        count = 0
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
                
            for link, title in zip(links[:limit], titles[:limit]):
                article = self._process_html(link, title)
                if article:
                    yield article
                    count += 1

            LAST_SCRAPE.set_to_current_time()
        except Exception as e:
            self.driver.save_screenshot(f"output/investing_error.png")
            print(f"An error occurred when reading new messages: {e}")
            SCRAPE_ERRORS.inc()
        finally:
            logger.info(f"Scraped {count} articles.")

    def _start_driver(self):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")

        hub_url = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444/wd/hub")
        logger.info(f"Using Selenium Hub URL: {hub_url}")
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
        wait = WebDriverWait(self.driver, 10)
        self.driver.get("https://www.tradingview.com/#signin")

        try:
            logger.info("Waiting for 'Email' button...")
            email_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='Email']"))
            )

            logger.info("Clicking 'Email' button.")
            email_button.click()

            logger.info("Waiting for username field...")
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

            logger.info("Waiting for dashboard...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))

            self._save_cookies()
            logger.info("Logged in successfully.")
            return True

        except Exception as e:
            logger.error("Login failed with exception:")
            traceback.print_exc()
            self.driver.quit()
            return False

    def _extract_article(self, html_text):
        soup = BeautifulSoup(html_text, 'html.parser')

        title = soup.find('h1', class_='title-KX2tCBZq')
        content = soup.find('div', class_='body-KX2tCBZq')

        return {
            "title": title.text.strip() if title else "No Title",
            "content": "\n".join(p.get_text(strip=True) for p in content.find_all('p')) if content else "No Content"
        }

    @cached_fetcher(20)
    def _process_html(self, link: str, title: str) -> Optional[dict]:
        # Skip if article is already in cache
        if self.article_cache.get(link):
            logger.info(f"Skipping cached article: {link}")
            return

        logger.info(f"Reading new article.")
        logger.info(f"title: {title}\nlink: {link}\n")

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
            logger.info(f"Saved HTML to {html_path}")
            
            article = self._extract_article(html_content)
            return article
        except Exception as e:
            logger.error(f"Failed to read article: {e}")

def scraper_worker(loop: asyncio.AbstractEventLoop, message_queue: asyncio.Queue, stop_event: asyncio.Event, username: str, password: str):

    with TradingViewScraper(username=username, password=password) as scraper:
        if not scraper.login():
            logger.error("tradingview login failed.")
            return
        
        while not stop_event.is_set():
            try:
                for article in scraper.fetch_news(limit=5):
                    if article:
                        loop.call_soon_threadsafe(asyncio.create_task, message_queue.put(article))
                time.sleep(10)
            except Exception as e:
                logger.error(f"Failed to fetch news: {e}")
                time.sleep(1)

async def article_publisher(channel: aio_pika.channel.Channel, message_queue: asyncio.Queue, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            article = await asyncio.wait_for(message_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            continue
        if article:
            try:
                logger.info(f"Publishing article: {article}")
                await channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(article).encode()),
                    routing_key=QUEUE_TV_ARTICLES
                )
            except Exception as e:
                logger.error(f"Failed to publish article: {e}, return to queue")
                await message_queue.put(article)
            finally:
                message_queue.task_done()
            

async def main():

    username = os.getenv("TRADE_VIEW_USER")
    password = os.getenv("TRADE_VIEW_PASS")    
    if not username or not password:
        logger.error("Missing credentials. Set TRADE_VIEW_USER and TRADE_VIEW_PASS in your environment.")
        return

    loop = asyncio.get_event_loop()
    thread_stop = threading.Event()
    message_queue = asyncio.Queue()
    loop_stop = asyncio.Event()

    def _stop(signum, frame):
        logger.info("Gracefully shutting down for signal {signum}")
        thread_stop.set()
        loop.call_soon_threadsafe(loop_stop.set)
    
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    
    # Start scraper thread
    scraper_thread = threading.Thread(target=scraper_worker, args=(loop, message_queue, thread_stop, username, password))
    scraper_thread.start()
    
    # Start message consumer
    channel = await new_mq_channel(QUEUE_TV_ARTICLES)
    asyncio.create_task(article_publisher(channel, message_queue, loop_stop))

    await loop_stop.wait()
    
    logger.info("Shutting down, waiting for queue to drain")
    await message_queue.join()

    logger.info("Shutting down RabbitMQ connection")
    await channel.close()

    logger.info("Shutting down scraper thread")
    scraper_thread.join(timeout=5)

if __name__ == "__main__":
    asyncio.run(main())