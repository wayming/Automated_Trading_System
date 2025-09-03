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
from .common import cached_fetcher, new_mq_channel
from singleton_logger import SafeSingletonLogger

QUEUE_TV_ARTICLES = "tv_articles"

SCRAPE_COUNT = Counter("scraper_runs_total", "Number of scraper runs")
SCRAPE_ERRORS = Counter("scraper_errors_total", "Number of errors during scraping")
LAST_SCRAPE = Gauge("scraper_last_scrape_timestamp", "Last scrape time (unix)")

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
        self.output_dir = "output/trading_view"
        os.makedirs(self.output_dir, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
        self.driver = None

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
                SafeSingletonLogger.info("Logged in using saved cookies.")

                return True
            except Exception:
                SafeSingletonLogger.error("Failed to login with cookies. Logging in manually.")
                traceback.print_exc()  # shows full traceback
                self.driver.quit()
                self.driver = None
                return False

        # Start fresh and log in
        return self._new_login()

    def fetch_news(self, limit=5) -> List[dict]:
        SafeSingletonLogger.section("Starting new scan(www.tradingview.com)")
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
            SafeSingletonLogger.error(f"An error occurred when reading new messages: {e}")
            SCRAPE_ERRORS.inc()
        finally:
            SafeSingletonLogger.info(f"Scraped {count} articles.")

    def _start_driver(self):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")

        hub_url = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444/wd/hub")
        SafeSingletonLogger.info(f"Using Selenium Hub URL: {hub_url}")
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
            SafeSingletonLogger.info("Waiting for 'Email' button...")
            email_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='Email']"))
            )

            SafeSingletonLogger.info("Clicking 'Email' button.")
            email_button.click()

            SafeSingletonLogger.info("Waiting for username field...")
            wait.until(EC.presence_of_element_located((By.ID, "id_username")))

            self.driver.find_element(By.ID, "id_username").send_keys(self.username)
            self.driver.find_element(By.ID, "id_password").send_keys(self.password)

            SafeSingletonLogger.info("Waiting for sign-in button...")
            sign_in_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Sign in']]"))
            )
            sign_in_button.click()

            SafeSingletonLogger.info("Waiting for dashboard...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))

            self._save_cookies()
            SafeSingletonLogger.info("Logged in successfully.")
            return True

        except Exception as e:
            SafeSingletonLogger.error("Login failed with exception:")
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

        SafeSingletonLogger.info(f"Reading new article.")
        SafeSingletonLogger.info(f"title: {title}\nlink: {link}\n")

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
            SafeSingletonLogger.info(f"Saved HTML to {html_path}")
            
            article = self._extract_article(html_content)
            return article
        except Exception as e:
            SafeSingletonLogger.error(f"Failed to read article: {e}")

def scraper_worker(loop: asyncio.AbstractEventLoop, message_queue: asyncio.Queue, stop_event: threading.Event, username: str, password: str):

    with TradingViewScraper(username=username, password=password) as scraper:
        giveup_time = time.time() + 60
        while not scraper.login():
            SafeSingletonLogger.error("tradingview login failed. Retrying...")
            if time.time() > giveup_time:
                SafeSingletonLogger.error("tradingview login failed. Give up.")
                return
            stop_event.wait(5)

        # fetch news every 10 seconds unless stop_event is set
        while not stop_event.wait(10):
            try:
                for article in scraper.fetch_news(limit=5):
                    if article:
                        asyncio.run_coroutine_threadsafe(message_queue.put(article), loop)
            except Exception as e:
                SafeSingletonLogger.error(f"Failed to fetch news: {e}")


async def article_publisher(channel: aio_pika.channel.Channel, message_queue: asyncio.Queue, stop_event: asyncio.Event):
    while not (stop_event.is_set() and message_queue.empty()): # break when stop_event is set and message_queue is empty, allow queue to drain
        try:
            article = await asyncio.wait_for(message_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            continue
        if article:
            try:
                await SafeSingletonLogger.ainfo(f"Publishing article: {article['title']}")
                await channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(article).encode()),
                    routing_key=QUEUE_TV_ARTICLES
                )
            except aio_pika.exceptions.AMQPError as e:
                await SafeSingletonLogger.aerror(f"Queue error: {e}")
                await message_queue.put(article)
                break
            except Exception as e:
                await SafeSingletonLogger.aerror(f"Failed to publish article: {e}, return to queue")
                await asyncio.sleep(5)
                await message_queue.put(article)
            finally:
                message_queue.task_done()
            

async def main():
    SafeSingletonLogger("output/trading_view_scraper.log")
    SafeSingletonLogger.info("Starting scraper")
    username = os.getenv("TRADE_VIEW_USER")
    password = os.getenv("TRADE_VIEW_PASS")    
    if not username or not password:
        await SafeSingletonLogger.aerror("Missing credentials. Set TRADE_VIEW_USER and TRADE_VIEW_PASS in your environment.")
        return

    loop = asyncio.get_event_loop()
    thread_stop = threading.Event()
    message_queue = asyncio.Queue()
    loop_stop = asyncio.Event()

    def _stop(signum, frame):
        SafeSingletonLogger.ainfo(f"Gracefully shutting down for signal {signum}")
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
    
    await SafeSingletonLogger.ainfo("Shutting down, waiting for queue to drain")
    await message_queue.join()

    await SafeSingletonLogger.ainfo("Shutting down RabbitMQ connection")
    await channel.close()

    SafeSingletonLogger.ainfo("Shutting down scraper thread")
    scraper_thread.join(timeout=5)

if __name__ == "__main__":
    asyncio.run(main())