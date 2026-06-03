import json
import sys
import random
import urllib.parse
from playwright.sync_api import sync_playwright

def run():
    limit = 300
    arg = urllib.parse.quote("전포동 맛집")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--window-position=-32000,-32000", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = context.new_page()
            
            results = []
            seen_mids = set()
            
            def handle_response(response):
                try:
                    url = response.url
                    places = []
                    if "api/search/allSearch" in url and response.status == 200:
                        data = response.json()
                        places = data.get("result", {}).get("place", {}).get("list", [])
                        print(f"Intercepted allSearch! Found {len(places)} items.")
                    elif "pcmap-api.place.naver.com/graphql" in url and response.status == 200:
                        data = response.json()
                        if isinstance(data, list):
                            data = data[0]
                        d_data = data.get("data", {})
                        for k, v in d_data.items():
                            if isinstance(v, dict) and "businesses" in v:
                                p_list = v["businesses"].get("items", [])
                                places.extend(p_list)
                        print(f"Intercepted graphql! Found {len(places)} items.")
                    else:
                        return
                        
                    for p_data in places:
                        mid = p_data.get("id")
                        if mid and mid not in seen_mids:
                            seen_mids.add(mid)
                            results.append(mid)
                except Exception as e:
                    print("Error parsing response:", e)
                        
            page.on("response", handle_response)
            
            page.goto(f"https://map.naver.com/p/search/{arg}", wait_until="domcontentloaded")
            
            try:
                page.wait_for_selector("#searchIframe", timeout=15000)
                iframe = page.frame_locator("#searchIframe")
                iframe.locator(".place_bluelink, .UEzoS").first.wait_for(timeout=15000)
            except Exception as e:
                print("Initial load wait error:", e)
            
            print(f"Page 1 loaded. len(results)={len(results)}")
            
            for i in range(2, 7):
                if len(results) >= limit:
                    break
                
                try:
                    iframe = page.frame_locator("#searchIframe")
                    print(f"Scrolling for page {i-1}...")
                    for s in range(6):
                        iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)")
                        page.wait_for_timeout(800)
                    
                    print(f"Scrolling done. len(results)={len(results)}. Clicking page {i}...")
                    
                    clicked = iframe.locator("body").evaluate(f'''body => {{
                        let links = Array.from(body.querySelectorAll("a, button"));
                        let btn = links.find(el => el.innerText.trim() === "{i}" || el.innerText.trim() === "{i}페이지" || el.innerText.trim() === "페이지 {i}" || (el.textContent && el.textContent.trim() === "{i}"));
                        if (btn) {{
                            btn.click();
                            return true;
                        }}
                        return false;
                    }}''')
                    
                    print(f"Clicked page {i}: {clicked}")
                    if clicked:
                        page.wait_for_timeout(3500)
                    else:
                        break
                except Exception as e:
                    print(f"Error on page {i}: {e}")
                    break
                        
            browser.close()
            print(f"Total results: {len(results)}")
            
    except Exception as e:
        print("Fatal error:", e)

if __name__ == "__main__":
    run()
