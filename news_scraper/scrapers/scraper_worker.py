import asyncio
import threading
import time
from common.logger import SingletonLoggerSafe
from common.interface import ScraperContext

LOGIN_RETRY_TIMEOUT = 60
SCRAPE_INTERVAL = 10
def scraper_worker(
    loop: asyncio.AbstractEventLoop,
    message_queue: asyncio.Queue,
    stop_event: threading.Event,
    context: ScraperContext):

    with context as scraper:
        giveup_time = time.time() + LOGIN_RETRY_TIMEOUT
        while not scraper.login():
            SingletonLoggerSafe.error("tradingview login failed. Retrying...")
            if time.time() > giveup_time:
                SingletonLoggerSafe.error("tradingview login failed. Give up.")
                return
            stop_event.wait(5)

        # fetch news every SCRAPE_INTERVAL seconds unless stop_event is set
        while not stop_event.wait(SCRAPE_INTERVAL):
            try:
                for article in scraper.fetch_news(limit=5):
                    if article:
                        asyncio.run_coroutine_threadsafe(message_queue.put(article), loop)
            except Exception as e:
                SingletonLoggerSafe.error(f"Failed to fetch news: {e}")