import json
import sys
from playwright.sync_api import sync_playwright

q = "전포동 맛집"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page.goto(f'https://map.naver.com/p/search/{q}', wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    page.screenshot(path='screenshot2.png', full_page=True)
    
    try:
        iframe = page.frame_locator("#searchIframe")
        html = iframe.locator("body").inner_html()
        with open("searchIframe.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Iframe dumped successfully.")
    except Exception as e:
        print("Iframe dump failed:", e)
        
    browser.close()
