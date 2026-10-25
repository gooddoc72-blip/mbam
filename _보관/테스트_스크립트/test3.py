import asyncio
from playwright.async_api import async_playwright
async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            res = await page.evaluate("""() => { return /\\/[^/]+\\/\\d+/.test('/a/123'); }""")
            print('RESULT:', res)
        except Exception as e:
            print('ERROR:', e)
        finally:
            await browser.close()
asyncio.run(test())
