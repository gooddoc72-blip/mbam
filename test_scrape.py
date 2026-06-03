import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        await page.goto("https://search.shopping.naver.com/search/all?query=씨솔트초콜릿&pagingIndex=1&pagingSize=40", wait_until="networkidle", timeout=15000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        items = await page.query_selector_all("[class^='product_item__'], [class^='basicList_item__']")
        
        for idx, item in enumerate(items[:3]):
            html_content = await item.inner_text()
            html_content = html_content.replace('\n', ' ')
            print(f"--- Item {idx+1} ---")
            print(html_content)
            
            review_match = re.search(r'\(([\d,]+)\)', html_content)
            purchase_match = re.search(r'구매\s*([\d,]+)', html_content)
            keep_match = re.search(r'찜\s*([\d,]+)', html_content)
            
            print('Parsed -> Reviews:', review_match.group(1) if review_match else 'None',
                  'Purchases:', purchase_match.group(1) if purchase_match else 'None',
                  'Keeps:', keep_match.group(1) if keep_match else 'None')
            
        await browser.close()

asyncio.run(main())
