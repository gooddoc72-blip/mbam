import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

options = uc.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--start-maximized')
driver_path = ChromeDriverManager().install()
driver = uc.Chrome(options=options, driver_executable_path=driver_path)

wait = WebDriverWait(driver, 10)
driver.get("https://map.naver.com/p/search/전포동 맛집")
time.sleep(5)
wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))
items = driver.find_elements(By.CSS_SELECTOR, "li.VLTHu, li.tzwk0, li.UEzoS, li.YwYLL")
item = items[0]
driver.execute_script("arguments[0].scrollIntoView();", item)
time.sleep(1)
driver.execute_script("arguments[0].click();", item)
time.sleep(3)

driver.switch_to.default_content()
wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe")))
with open("entry_dump.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)

driver.quit()
print("Done")
