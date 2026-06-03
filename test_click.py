import time, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    results = []
    
    def handle_response(response):
        if 'api/search/allSearch' in response.url and response.status == 200:
            try:
                data = response.json()
                places = data.get('result', {}).get('place', {}).get('list', [])
                results.extend(places)
                print(f'Intercepted {len(places)} items. Total: {len(results)}')
            except: pass
            
    page.on('response', handle_response)
    
    page.goto('https://map.naver.com/p/search/전포동맛집')
    try:
        page.wait_for_selector('#searchIframe', timeout=15000)
    except: pass
    iframe = page.frame_locator('#searchIframe')
    try:
        iframe.locator('.place_bluelink, .UEzoS').first.wait_for(timeout=15000)
    except: pass
    
    time.sleep(2) # wait for first response
    
    for i in range(2, 6):
        print(f'Attempting to click page {i}')
        # Scroll the container
        for _ in range(4):
            iframe.locator('#_pcmap_list_scroll_container').evaluate('el => el.scrollTo(0, el.scrollHeight)')
            time.sleep(0.5)
            
        try:
            # Try specific class first
            locator = iframe.locator(f'a.mBN2s:has-text("{i}")')
            if locator.count() > 0:
                locator.first.click(timeout=3000)
                print(f'Clicked page {i} using .mBN2s')
            else:
                iframe.locator(f'a:has-text("{i}")').last.click(timeout=3000)
                print(f'Clicked page {i} using fallback a:has-text')
            time.sleep(2)
        except Exception as e:
            print(f'Failed to click page {i}: {e}')
            
    # dump all names
    names = []
    for r in results:
        item = r.get('item', r)
        names.append(item.get('name'))
    with open('test_names.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(str(n) for n in names))
    print(f"Done. Wrote {len(names)} names.")
