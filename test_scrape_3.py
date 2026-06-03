import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        await page.goto("https://search.shopping.naver.com/search/all?query=씨솔트초콜릿&pagingIndex=1&pagingSize=40", wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(2000)
        html = await page.content()
        with open('naver_shopping_dump.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Dump saved.")
        await browser.close()

asyncio.run(main())
