import json
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

captured_headers = {}

def intercept(resp):
    global captured_headers
    if "api/search/allSearch" in resp.url and resp.status == 200:
        captured_headers = resp.request.all_headers()

q = urllib.parse.quote("전포동 맛집")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.on("response", intercept)
    page.goto(f"https://map.naver.com/p/search/{q}", wait_until="networkidle")
    page.wait_for_timeout(3000)
    browser.close()

print(json.dumps(captured_headers, indent=2))
