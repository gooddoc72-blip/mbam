import asyncio
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def test():
    a = SeoAnalyzer()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        desktop_context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = await a._setup_stealth_page(desktop_context, block_images=False)
        await page.goto('https://cafe.naver.com/ArticleRead.nhn?cluburl=cjyeonsu&articleid=574961')
        await page.wait_for_timeout(3000)
        html = await page.content()
        with open('cafe_stealth_dump.html', 'w', encoding='utf-8') as f:
            f.write(html)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(test())
