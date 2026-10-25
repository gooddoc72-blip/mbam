import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        await page.goto("https://search.shopping.naver.com/search/all?query=씨솔트초콜릿&pagingIndex=1&pagingSize=40", wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        with open('naver_shopping_dump_ok.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Dumped ok.")
                      
        await browser.close()

asyncio.run(main())
