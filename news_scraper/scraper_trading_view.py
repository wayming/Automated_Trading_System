import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import time
from collections import OrderedDict
import re
import sys
import os
import pickle

COOKIES_PATH = "output/cookies.pkl"

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> bool:
        if key not in self.cache:
            return False
        self.cache.move_to_end(key)
        return True

    def put(self, key: str) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)
        self.cache[key] = True

# Initialize LRU cache with capacity of 20
article_cache = LRUCache(20)


def save_cookies(driver, path):
    with open(path, "wb") as file:
        pickle.dump(driver.get_cookies(), file)

def load_cookies(driver, path):
    with open(path, "rb") as file:
        cookies = pickle.load(file)
        for cookie in cookies:
            driver.add_cookie(cookie)

def start_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)
    return driver

def login_to_tradingview(username, password, driver):
    wait = WebDriverWait(driver, 200)
    driver.get("https://www.tradingview.com/#signin")

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Email']")))
        driver.find_element(By.XPATH, "//span[text()='Email']").click()

        wait.until(EC.presence_of_element_located((By.NAME, "id_username")))
        driver.find_element(By.NAME, "id_username").send_keys(username)
        driver.find_element(By.NAME, "id_password").send_keys(password + Keys.RETURN)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))
        print("[+] Logged in successfully.")
        input("Please complete login manually in the browser, then press Enter to continue...")
        save_cookies(driver, COOKIES_PATH)
        return True
    except Exception as e:
        print(f"[!] Login failed: {e}")
        return False

def auto_login_tradingview(username, password):
    driver = start_driver()

    if os.path.exists(COOKIES_PATH):
        driver.get("https://www.tradingview.com")
        try:
            load_cookies(driver, COOKIES_PATH)
            driver.refresh()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts"))
            )
            print("[+] Logged in using saved cookies.")
            input("Please complete login manually in the browser, then press Enter to continue...")

            return driver
        except Exception:
            print("[!] Failed to login with cookies. Logging in manually.")
            driver.quit()

    # Start fresh and log in
    if login_to_tradingview(username, password, driver):
        return driver
    else:
        driver.quit()
        return None

def debug_tradingview_login(username, password):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/accounts/signin/"
    }

    # First get the login page to obtain cookies and CSRF token
    print("🛠️ Step 1: Getting login page...")
    login_page = session.get("https://www.tradingview.com/accounts/signin/", headers=headers)
    print(f"Initial cookies: {session.cookies.get_dict()}")

    # Try to find CSRF token in the response
    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    if csrf_token:
        print(f"🔑 Found CSRF token: {csrf_token['value']}")
    else:
        print("⚠️ No CSRF token found")

    # Prepare login data
    login_data = {
        "username": username,
        "password": password,
        "remember": "on"
    }
    if csrf_token:
        login_data["csrfmiddlewaretoken"] = csrf_token["value"]

    # Attempt login
    print("\n🛠️ Step 2: Attempting login...")
    login_response = session.post(
        "https://www.tradingview.com/accounts/signin/",
        data=login_data,
        headers=headers,
        allow_redirects=False  # Important to see the true response
    )
    
    print(f"Login response status: {login_response.status_code}")
    print(f"Response cookies: {login_response.cookies.get_dict()}")
    print(f"Redirect location: {login_response.headers.get('Location')}")

    # Check for successful auth cookies
    auth_cookies = session.cookies.get_dict()
    print("\n🔍 Final session cookies:")
    for k, v in auth_cookies.items():
        print(f"{k}: {v}")

    # Test authenticated request
    if login_response.status_code == 302:  # Expecting redirect on success
        print("\n🛠️ Step 3: Testing authenticated request...")
        test_url = "https://www.tradingview.com/account/#profile"
        profile_response = session.get(test_url, headers=headers)
        print(f"Profile page status: {profile_response.status_code}")
        print(f"Contains username? {'username' in profile_response.text.lower()}")
    else:
        print("\n⚠️ Login likely failed - check response details above")

def slugify_filename(text, max_length=100):
    text = text.strip("'")
    # Replace special characters with underscores
    text = re.sub(r'[<>:"/\\|?*\s,\.]', '_', text)
    # Trim to max length
    return text[:max_length]

def read_message(driver):
    print("\n" + "="*50)
    print(f"Starting new scan at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    file_paths = []
    try:
        # 1. Visit TradingView News Flow
        driver.get("https://www.tradingview.com/news-flow/")
        time.sleep(5)  # wait for JS content to load

        # 2. Get all news <a> links
        news_elements = driver.find_elements("css selector", ".card-HY0D0owe")
        links = [el.get_attribute("href") for el in news_elements if el.get_attribute("href")]
        titles = [el.find_element(By.CSS_SELECTOR, ".title-HY0D0owe").text for el in news_elements]
        # 3. Use BeautifulSoup to extract each article's content
        new_articles_found = 0
        for url, title in zip(links[:5], titles[:5]):  # limit for demo (first 5)
            # Skip if article is already in cache
            if article_cache.get(url):
                print(f"\n⏩ Skipping cached article: {url}")
                continue

            print(f"\n🔗 Reading new article: {url}")
            
            driver.get(url)
            time.sleep(5)
            fname = slugify_filename(title)
            
            # Wait for article content
            wait = WebDriverWait(driver, 5)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".body-KX2tCBZq")))
            # input("Please check news in the browser, then press Enter to continue...")
            print("[+] News read successfully.")
            driver.save_screenshot(f"output/{fname}.png")

            # 8. Save page HTML to file
            print(f"\n🔗 Write to file: {fname}")
            with open(f"output/{fname}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"[+] Saved full HTML to output/{fname}.html.")
            file_paths.append(f"output/{fname}.html")

            # Add to cache
            article_cache.put(url)
            new_articles_found += 1
            
        if new_articles_found == 0:
            print("\nℹ️ No new articles found in this scan")
            
    except Exception as e:
        print(f"⚠️ An error occurred: {str(e)}")

    return file_paths

def tradingview_login(username, password):
 
    # Set up Chrome options
    options = uc.ChromeOptions()
    # Comment this out to see the browser (recommended for debugging)
    # options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Start WebDriver
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 200)

    try:
        # 1. Go to TradingView login page
        driver.get("https://www.tradingview.com/#signin")
        wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Email']")))

        # 2. Click "Email" login option
        email_button = driver.find_element(By.XPATH, "//span[text()='Email']")
        email_button.click()

        # 3. Fill in login form
        wait.until(EC.presence_of_element_located((By.NAME, "id_username")))
        email_input = driver.find_element(By.NAME, "id_username")
        password_input = driver.find_element(By.NAME, "id_password")

        email_input.send_keys(USERNAME)
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.RETURN)

        # 4. Wait for login to complete
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-lightweight-charts")))
        print("[+] Logged in successfully.")
        driver.save_screenshot("output/afterlogin.png")

        return driver
    
    except Exception as e:
        print(e)
        driver.quit()
    
    return None

def main():
    # Usage
    USERNAME = os.getenv("TRADE_VIEW_USER")
    PASSWORD = os.getenv("TRADE_VIEW_PASS")
    driver = auto_login_tradingview(USERNAME, PASSWORD)
    if not driver:
        print('no driver')
        sys.exit(1)

    # Run the function in a loop with 3-second delay
    while True:
        news = read_message(driver)
        for n in news:
            print(n)
        print("\n" + "="*50)
        print(f"Cache size: {len(article_cache.cache)}/20 | Waiting 3 seconds before next scan...")
        print("="*50 + "\n")
        time.sleep(3)