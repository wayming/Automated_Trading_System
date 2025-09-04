import os
import asyncio
import threading
import signal

from prometheus_client import Counter
from prometheus_client import Gauge

from scrapers.trade_view import TVScraperContext
from scrapers.scraper_worker import scraper_worker
from scrapers.publish_worker import article_publisher
from common.utils import new_mq_channel
from common.logger import SingletonLoggerSafe
from common.utils import new_webdriver


SCRAPE_COUNT = Counter("scraper_runs_total", "Number of scraper runs")
SCRAPE_ERRORS = Counter("scraper_errors_total", "Number of errors during scraping")
LAST_SCRAPE = Gauge("scraper_last_scrape_timestamp", "Last scrape time (unix)")
QUEUE_TV_ARTICLES = "tv_articles"

async def main():
    SingletonLoggerSafe("output/scraper_trading_view.log")
    SingletonLoggerSafe.info("Starting scraper")
    username = os.getenv("TRADE_VIEW_USER")
    password = os.getenv("TRADE_VIEW_PASS")    
    if not username or not password:
        await SingletonLoggerSafe.aerror("Missing credentials. Set TRADE_VIEW_USER and TRADE_VIEW_PASS in your environment.")
        return

    hub_url = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444/wd/hub")
    if not hub_url:
        await SingletonLoggerSafe.aerror("Missing Selenium Hub URL. Set SELENIUM_HUB_URL in your environment.")
        return
    
    loop = asyncio.get_event_loop()
    thread_stop = threading.Event()
    message_queue = asyncio.Queue()
    loop_stop = asyncio.Event()

    def _stop(signum, frame):
        SingletonLoggerSafe.info(f"Gracefully shutting down for signal {signum}")
        thread_stop.set()
        loop.call_soon_threadsafe(loop_stop.set)
    
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    
    # Start scraper thread
    driver = new_webdriver(hub_url)
    scraper_context = TVScraperContext(driver, username, password)
    scraper_thread = threading.Thread(target=scraper_worker, args=(loop, message_queue, thread_stop, scraper_context))
    scraper_thread.start()
    
    # Start message consumer
    channel = await new_mq_channel()
    asyncio.create_task(article_publisher(channel, QUEUE_TV_ARTICLES, message_queue, loop_stop))

    await loop_stop.wait()
    
    await SingletonLoggerSafe.ainfo("Shutting down, waiting for queue to drain")
    await message_queue.join()

    await SingletonLoggerSafe.ainfo("Shutting down RabbitMQ connection")
    await channel.close()

    await SingletonLoggerSafe.ainfo("Shutting down scraper thread")
    scraper_thread.join(timeout=5)

if __name__ == "__main__":
    asyncio.run(main())