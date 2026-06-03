import asyncio
from playwright.async_api import async_playwright
import json

async def fetch_related():
    keyword = "동래맛집"
    url = f"https://m.search.naver.com/search.naver?where=m_blog&query={keyword}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36")
        await page.goto(url, timeout=10000)
        
        related = await page.evaluate('''() => {
            const els = document.querySelectorAll('.keyword_box_wrap .tit, .related_srch .tit, .relate_srch .tit, .keyword');
            return Array.from(els).map(el => el.innerText).filter(t => t.trim().length > 0);
        }''')
        
        print("Related:", related)
        await browser.close()

if __name__ == "__main__":
    if __import__('os').name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(fetch_related())
