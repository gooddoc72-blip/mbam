import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

options = uc.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--start-maximized')
driver = uc.Chrome(options=options)
driver.set_page_load_timeout(30)

print("Navigating to coupang...")
driver.get("https://www.coupang.com/")
time.sleep(5)

driver.save_screenshot("coupang_home_test.png")
print("Saved screenshot to coupang_home_test.png")

html = driver.page_source
with open("coupang_home_test.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Saved html to coupang_home_test.html")

try:
    search_box = driver.find_element(By.ID, "headerSearchKeyword")
    print("Found headerSearchKeyword!")
except Exception as e:
    print("Could not find headerSearchKeyword:", e)
    
driver.quit()
