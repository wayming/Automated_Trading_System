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

def tradingview_login(username, password):
    session = requests.Session()
    
    # TradingView login URL (check this is correct)
    login_url = "https://www.tradingview.com/accounts/signin/"
    
    login_data = {
        "username": username,
        "password": password,
        "remember": "on"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.tradingview.com"
    }
    
    try:
        # First get the login page to get cookies
        session.get(login_url, headers=headers)
        
        # Perform login
        response = session.post(login_url, data=login_data, headers=headers)
        print(response)
        response.raise_for_status()
        
        # Check if login was successful
        if "signin" in response.url:
            raise Exception("Login failed - check credentials")
            
        return session
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return None
    
def read_url(session, url):
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # TradingView specific selectors
        title = soup.select_one(".article-title, .title-H1bD1x_q, h1")
        if title:
            print(f"📌 Title: {title.text.strip()}")
        else:
            print("⚠️ Title not found")
            
        # Content extraction
        content = soup.select_one(".article-content, .content-RjfJG2be")
        if content:
            print("\n📝 Content:")
            for p in content.select("p"):
                text = p.text.strip()
                if text:
                    print(f"- {text}")
        else:
            print("⚠️ Content not found")
            
    except Exception as e:
        print(f"Error: {str(e)}")

def slugify_filename(text, max_length=100):
    # Replace spaces with underscores
    text = text.replace("/", "_")
    # Remove invalid characters for filenames
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    # Trim to max length
    return text[:max_length]

def read_message(driver):
    print("\n" + "="*50)
    print(f"Starting new scan at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    try:
        # 1. Visit TradingView News Flow
        driver.get("https://www.tradingview.com/news-flow/")
        time.sleep(5)  # wait for JS content to load

        # 2. Get all news <a> links
        news_elements = driver.find_elements("css selector", "a.card-HY0D0owe")
        links = [el.get_attribute("href") for el in news_elements if el.get_attribute("href")]

        # 3. Use BeautifulSoup to extract each article's content
        new_articles_found = 0
        for url in links[:5]:  # limit for demo (first 5)
            # Skip if article is already in cache
            if article_cache.get(url):
                print(f"\n⏩ Skipping cached article: {url}")
                continue
                
            print(f"\n🔗 Reading new article: {url}")
            
            driver.get(url)
            time.sleep(5)
            fname = slugify_filename(url)
            
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
            print("[+] Saved full HTML to 'tradingview_news_article.html'.")

            
            # Add to cache
            article_cache.put(url)
            new_articles_found += 1
            
        if new_articles_found == 0:
            print("\nℹ️ No new articles found in this scan")
            
    except Exception as e:
        print(f"⚠️ An error occurred: {str(e)}")




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
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-content")))
        input("Please complete login manually in the browser, then press Enter to continue...")
        print("[+] Logged in successfully.")
        driver.save_screenshot("output/afterlogin.png")
        
        return driver
    
    except Exception as e:
        driver.quit()
    
    return None

def get_authenticated_content(driver, url):
    driver.get(url)
    time.sleep(3)  # Wait for content to load
    
    # Get cookies for requests session
    cookies = driver.get_cookies()
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    
    # Now you can use either Selenium or the session for requests
    # Example with Selenium:
    content = driver.find_element(By.TAG_NAME, "body").text
    return content

# Usage
USERNAME = os.getenv("TRADE_VIEW_USER")
PASSWORD = os.getenv("TRADE_VIEW_PASS")
driver = tradingview_login(USERNAME, PASSWORD)
if not driver:
    print('no driver')
    sys.exit(1)

# Run the function in a loop with 3-second delay
while True:
    read_message(driver)
    print("\n" + "="*50)
    print(f"Cache size: {len(article_cache.cache)}/20 | Waiting 3 seconds before next scan...")
    print("="*50 + "\n")
    time.sleep(3)