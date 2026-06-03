import json
from playwright.sync_api import sync_playwright
import urllib.parse

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--window-position=-32000,-32000"])
    page = browser.new_page()
    page.goto(f"https://map.naver.com/p/search/{q}", wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    iframe = page.frame_locator("#searchIframe")
    
    html = iframe.locator("body").inner_html()
    with open("offscreen.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    print("Offscreen test completed.")
    browser.close()
