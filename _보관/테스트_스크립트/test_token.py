import json
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

first_url = ""
first_headers = {}

def intercept(resp):
    global first_url, first_headers
    if "api/search/allSearch" in resp.url and resp.status == 200 and not first_url:
        first_url = resp.url
        first_headers = resp.request.headers

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.on("response", intercept)
    page.goto(f"https://map.naver.com/p/search/{q}", wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    if first_url:
        # construct page 2 url
        if "&page=" in first_url:
            page2_url = first_url.replace("&page=1", "&page=2")
        else:
            page2_url = first_url + "&page=2"
            
        print("Page 2 URL:", page2_url)
        # execute fetch using playwright context so cookies are present
        res = page.evaluate(f'''async () => {{
            let r = await fetch("{page2_url}");
            if (r.ok) {{
                let j = await r.json();
                return j.result.place.list.length;
            }}
            return -1;
        }}''')
        print("Page 2 fetched items length:", res)

    browser.close()
