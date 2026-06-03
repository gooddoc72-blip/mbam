import asyncio
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://m.search.naver.com/search.naver?where=m_blog&query=전포동+맛집")
        await page.wait_for_selector('a[href*="blog.naver.com/"]')
        elements = await page.query_selector_all('a[href*="blog.naver.com/"]')
        for el in elements[:5]:
            href = await el.get_attribute('href')
            parent = await el.evaluate_handle('el => el.closest("li") || el.parentElement')
            text = await parent.inner_text() if parent else ""
            print("HREF:", href)
            print("TEXT:", text.replace("\\n", " ")[:50])
        await browser.close()

if __name__ == "__main__":
    if __import__("os").name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(check())
