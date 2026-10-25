import urllib.parse
from playwright.sync_api import sync_playwright

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(f'https://map.naver.com/p/search/{q}', wait_until='networkidle')
    page.wait_for_timeout(3000)
    html = page.locator('body').inner_html()
    with open('iframe_body.html', 'w', encoding='utf-8') as f:
        f.write(html)
    browser.close()
