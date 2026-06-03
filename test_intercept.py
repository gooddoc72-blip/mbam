import sys
import json
from playwright.sync_api import sync_playwright
import time

def test_pagination(keyword):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        results = []
        
        def handle_response(response):
            if "api/search/allSearch" in response.url and response.status == 200:
                try:
                    data = response.json()
                    places = data.get("result", {}).get("place", {}).get("list", [])
                    for p in places:
                        results.append({
                            "name": p.get("name"),
                            "mid": p.get("id"),
                            "rank": p.get("rank"),
                            "reviews": p.get("reviewCount", 0),
                            "saves": p.get("saveCount", 0)
                        })
                except Exception as e:
                    pass
                    
        page.on("response", handle_response)
        
        print(f"Going to search page for {keyword}...")
        page.goto(f"https://map.naver.com/p/search/{keyword}", wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Click pages 2 to 6
        for i in range(2, 7):
            try:
                page.locator(f".pagination > a:text('{i}')").click(timeout=3000)
                page.wait_for_timeout(2000)
            except:
                try:
                    page.locator(f"a:has-text('{i}')").last.click(timeout=3000)
                    page.wait_for_timeout(2000)
                except:
                    break
        
        print(f"Total places fetched: {len(results)}")
        if results:
            print(results[-1]['name'], results[-1]['mid'])
            
        browser.close()

if __name__ == "__main__":
    test_pagination("전포동 맛집")
