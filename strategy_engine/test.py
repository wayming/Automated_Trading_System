from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
driver = webdriver.Firefox(options=options)  # Selenium auto-finds the right driver
driver.get("https://www.whatismybrowser.com/")