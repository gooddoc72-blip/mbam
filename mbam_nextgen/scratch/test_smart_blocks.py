import asyncio
from playwright.async_api import async_playwright

async def get_smart_blocks(keyword):
    search_url = f"https://m.search.naver.com/search.naver?where=m_view&sm=mtb_jum&query={keyword}"
    # m_view usually contains more smart blocks than m_blog, but let's test m_view or m_search
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)")
        await page.goto(search_url)
        await page.wait_for_timeout(3000)
        
        # Smart block titles usually in .api_title, .tit_text, or .api_subject_bx .tit
        titles = await page.evaluate('''() => {
            const els = document.querySelectorAll('.api_title, .tit_text, .api_subject_bx .tit, .sp_nreview .tit');
            return Array.from(els).map(el => el.innerText.trim()).filter(t => t.length > 0);
        }''')
        
        print(f"Smart blocks for {keyword}:", list(set(titles)))
        await browser.close()

if __name__ == "__main__":
    if __import__("os").name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(get_smart_blocks("동래맛집"))
