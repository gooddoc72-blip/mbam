import json
import urllib.parse
from playwright.sync_api import sync_playwright

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--window-position=-32000,-32000"])
    page = browser.new_page()
    page.goto(f"https://map.naver.com/p/search/{q}", wait_until="domcontentloaded")
    
    try:
        page.wait_for_selector("#searchIframe", timeout=10000)
        iframe = page.frame_locator("#searchIframe")
        
        # Wait for the first place to load
        iframe.locator(".place_bluelink, .UEzoS").first.wait_for(timeout=10000)
        print("First page loaded!")
        
        # Scroll the container 6 times
        for _ in range(6):
            iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(800)
            
        # Try to click page 2
        clicked = iframe.locator("body").evaluate('''body => {
            let links = Array.from(body.querySelectorAll("a, button"));
            let btn = links.find(el => el.innerText.trim() === "2" || el.innerText.trim() === "2페이지" || el.innerText.trim() === "페이지 2" || (el.textContent && el.textContent.trim() === "2"));
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        }''')
        
        print("Page 2 clicked:", clicked)
        if clicked:
            page.wait_for_timeout(3000)
            
    except Exception as e:
        print("Error:", e)
        
    browser.close()
