import urllib.parse
from playwright.sync_api import sync_playwright

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    page = context.new_page()
    page.goto(f'https://map.naver.com/p/search/{q}', wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    iframe = page.frame_locator("#searchIframe")
    
    # Scroll multiple times to load items and trigger pagination render
    for _ in range(6):
        iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)")
        page.wait_for_timeout(800)
    
    html = iframe.locator("body").inner_html()
    with open('true_pagination_scrolled.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
    browser.close()
