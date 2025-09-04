import os
import traceback
import pickle
import re

from typing import List, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by  import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support    import expected_conditions as EC
from selenium.webdriver import Remote as RemoteWebDriver
from selenium.webdriver.chrome.options import Options
from common.logger import SingletonLoggerSafe
from common.interface import NewsScraper, ScraperFactory
from common.utils import cached_fetcher

class TVScraperFactory(ScraperFactory):
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
    
    def create_scraper(self) -> NewsScraper:
        return TradingViewScraper(username=self.username, password=self.password)

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
                SingletonLoggerSafe.info("Logged in using saved cookies.")

                return True
            except Exception:
                SingletonLoggerSafe.error("Failed to login with cookies. Logging in manually.")
                traceback.print_exc()  # shows full traceback
                self.driver.quit()
                self.driver = None
                return False

        # Start fresh and log in
        return self._new_login()

    def fetch_news(self, limit=5) -> List[dict]:
        SingletonLoggerSafe.section("Starting new scan(www.tradingview.com)")
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

        except Exception as e:
            self.driver.save_screenshot(f"output/investing_error.png")
            SingletonLoggerSafe.error(f"An error occurred when reading new messages: {e}")
        finally:
            SingletonLoggerSafe.info(f"Scraped {count} articles.")

    def _start_driver(self):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")

        hub_url = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444/wd/hub")
        SingletonLoggerSafe.info(f"Using Selenium Hub URL: {hub_url}")
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
            SingletonLoggerSafe.info("Waiting for 'Email' button...")
            email_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='Email']"))
            )

            SingletonLoggerSafe.info("Clicking 'Email' button.")
            email_button.click()

            SingletonLoggerSafe.info("Waiting for username field...")
            wait.until(EC.presence_of_element_located((By.ID, "id_username")))

            self.driver.find_element(By.ID, "id_username").send_keys(self.username)
            self.driver.find_element(By.ID, "id_password").send_keys(self.password)

            SingletonLoggerSafe.info("Waiting for sign-in button...")
            sign_in_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Sign in']]"))
            )
            sign_in_button.click()

            SingletonLoggerSafe.info("Waiting for dashboard...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))

            self._save_cookies()
            SingletonLoggerSafe.info("Logged in successfully.")
            return True

        except Exception as e:
            SingletonLoggerSafe.error("Login failed with exception:")
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

        SingletonLoggerSafe.info(f"Reading new article.")
        SingletonLoggerSafe.info(f"title: {title}\nlink: {link}\n")

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
            SingletonLoggerSafe.info(f"Saved HTML to {html_path}")
            
            article = self._extract_article(html_content)
            return article
        except Exception as e:
            SingletonLoggerSafe.error(f"Failed to read article: {e}")