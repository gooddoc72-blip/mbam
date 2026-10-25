import asyncio
from playwright.async_api import async_playwright

async def main():
    place_url = "https://m.place.naver.com/place/1468999371/home"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        
        print("Navigating to:", place_url)
        await page.goto(place_url)
        await asyncio.sleep(3)
        print("Clicking Review tab...")
        
        # Click the tab that contains "리뷰"
        try:
            tabs = await page.locator("a[role='tab']").all()
            for tab in tabs:
                text = await tab.inner_text()
                if "리뷰" in text:
                    await tab.click()
                    break
        except Exception as e:
            print("Tab click failed:", e)
            
        await asyncio.sleep(3)
        items = await page.locator("li").all()
        print("Total LI tags:", len(items))
        
        reviews = []
        for li in items:
            try:
                text = await li.inner_text()
                if len(text) > 10 and "방문자 리뷰" not in text:
                    reviews.append(text[:50].replace('\n', ' '))
            except:
                pass
                
        print("Found possible reviews:", len(reviews))
        if reviews:
            print(reviews[:3])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
