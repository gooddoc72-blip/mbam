import json
import urllib.parse
from playwright.sync_api import sync_playwright

def run():
    q = urllib.parse.quote("전포동 맛집")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--window-position=-32000,-32000", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        def on_res(r):
            if "api/search/allSearch" in r.url and r.status == 200:
                try:
                    data = r.json()
                    places = data.get("result", {}).get("place", {}).get("list", [])
                    print(f"allSearch fired: URL={r.url[-30:]}, count={len(places)}")
                except Exception as e:
                    print("Error parsing json:", e)
                    
        page.on("response", on_res)
        
        page.goto(f"https://map.naver.com/p/search/{q}", wait_until="domcontentloaded")
        page.wait_for_selector("#searchIframe", timeout=15000)
        iframe = page.frame_locator("#searchIframe")
        iframe.locator(".place_bluelink, .UEzoS").first.wait_for(timeout=15000)
        
        print("Scroling...")
        for _ in range(6):
            iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(800)
            
        print("Clicking 2...")
        clicked = iframe.locator("body").evaluate('''body => {
            let links = Array.from(body.querySelectorAll("a, button"));
            let btn = links.find(el => el.innerText.trim() === "2" || el.innerText.trim() === "2페이지" || (el.textContent && el.textContent.trim() === "2"));
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        }''')
        print("Clicked:", clicked)
        page.wait_for_timeout(5000)
        browser.close()

if __name__ == "__main__":
    run()
