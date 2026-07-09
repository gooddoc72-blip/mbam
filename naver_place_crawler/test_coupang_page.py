import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

options = uc.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--start-maximized')
options.add_argument('--accept-lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7')
driver = uc.Chrome(options=options)

try:
    driver.get('https://www.coupang.com/')
    time.sleep(2)
    search_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#headerSearchKeyword, input[name=\'q\'], input[type=\'search\']')))
    driver.execute_script('arguments[0].click();', search_box)
    search_box.clear()
    driver.execute_script('arguments[0].value = \'\';', search_box)
    search_box.send_keys('디퓨저')
    search_box.send_keys(Keys.ENTER)
    time.sleep(4)
    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
    time.sleep(2)
    
    pagination = driver.find_elements(By.CSS_SELECTOR, '.search-pagination, .pagination, [class*=\'pagination\']')
    if pagination:
        print('PAGINATION FOUND:')
        print(pagination[0].get_attribute('outerHTML'))
    else:
        print('NO PAGINATION FOUND!')
        
    print('A TAGS WITH 2:')
    tags = driver.find_elements(By.CSS_SELECTOR, 'a, button')
    for t in tags:
        text = t.text.strip()
        if '2' == text:
            print(f'TEXT: {text}, HREF: {t.get_attribute("href")}, CLASS: {t.get_attribute("class")}')
            
except Exception as e:
    print(e)
finally:
    driver.quit()
