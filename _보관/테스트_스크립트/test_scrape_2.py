import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        await page.goto("https://search.shopping.naver.com/search/all?query=씨솔트초콜릿&pagingIndex=1&pagingSize=40", wait_until="networkidle", timeout=15000)
        
        # Or look for an item container by finding '찜' or '리뷰'
        item = await page.query_selector('text="찜"')
        if item:
            parent = await item.evaluate_handle('node => { let cur = node; while(cur && !cur.className.includes("item__")) { cur = cur.parentElement; } return cur; }')
            if parent:
                parent_cls = await parent.evaluate('node => node.className')
                print('Found parent class:', parent_cls)
            else:
                print('Parent not found.')
        else:
            print('Text 찜 not found.')
            
        await browser.close()

asyncio.run(main())
