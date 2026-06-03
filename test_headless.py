import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        await page.goto("https://search.shopping.naver.com/search/all?query=씨솔트초콜릿&pagingIndex=1&pagingSize=40", wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(2000)
        
        items = await page.query_selector_all("[class^='product_item__'], [class^='basicList_item__'], [class^='adProduct_item__']")
        print(f'Found {len(items)} items with headless=False.')
        if items:
            for idx, item in enumerate(items[:3]):
                text = await item.inner_text()
                text = text.replace('\n', ' ')
                
                review_match = re.search(r'\(([\d,]+)\)', text)
                purchase_match = re.search(r'구매\s*([\d,]+)', text)
                keep_match = re.search(r'찜\s*([\d,]+)', text)
                
                print(f'--- Item {idx+1} ---')
                print('Reviews:', review_match.group(1) if review_match else 'None',
                      'Purchases:', purchase_match.group(1) if purchase_match else 'None',
                      'Keeps:', keep_match.group(1) if keep_match else 'None')
                      
        await browser.close()

asyncio.run(main())
