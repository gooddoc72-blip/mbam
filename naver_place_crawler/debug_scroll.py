import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import random

def test():
    options = uc.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--accept-lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7')
    # Add stealth options
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = uc.Chrome(options=options)
    
    try:
        driver.get('https://www.coupang.com/')
        time.sleep(3)
        search_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#headerSearchKeyword, input[name=\'q\'], input[type=\'search\']')))
        driver.execute_script('arguments[0].click();', search_box)
        time.sleep(1)
        search_box.clear()
        driver.execute_script('arguments[0].value = \'\';', search_box)
        for char in '요가':
            search_box.send_keys(char)
            time.sleep(0.1)
        search_box.send_keys(Keys.ENTER)
        time.sleep(4)
        
        print("Scrolled 0: ", len(driver.find_elements(By.CSS_SELECTOR, "li.search-product")))
        
        # Smooth scroll down
        for attempt in range(10):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)
            print(f"Scrolled {attempt+1}: ", len(driver.find_elements(By.CSS_SELECTOR, "li.search-product")))
            
            elements = driver.find_elements(By.CSS_SELECTOR, ".search-pagination, .btn-page")
            if elements:
                print("Pagination found!")
                for el in elements:
                    print("Class:", el.get_attribute("class"), "Text:", el.text)
                break
        else:
            print("Pagination NOT found. Dumping HTML to debug_coupang.html")
            with open("debug_coupang.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
                
    except Exception as e:
        print("Error:", e)
    finally:
        driver.quit()

if __name__ == '__main__':
    test()
