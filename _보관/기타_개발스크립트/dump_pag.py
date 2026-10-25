from playwright.sync_api import sync_playwright

def dump():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://map.naver.com/p/search/%EA%B4%91%EC%95%88%EB%A6%AC%20%EB%A7%9B%EC%A7%91', wait_until='networkidle')
        iframe = page.frame_locator('#searchIframe')
        page.wait_for_timeout(2000)
        
        # Scroll to bottom
        for _ in range(3):
            iframe.locator('#_pcmap_list_scroll_container').evaluate('el => el.scrollTo(0, el.scrollHeight)')
            page.wait_for_timeout(1000)
            
        # Check all possible pagination classes
        html = iframe.locator('body').inner_html()
        with open('body_dump.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        print("Done dumping.")
        browser.close()

if __name__ == '__main__':
    dump()
