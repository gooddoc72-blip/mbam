import asyncio
from playwright.async_api import async_playwright
import json

async def inspect_naver_search():
    search_url = "https://m.search.naver.com/search.naver?where=m_blog&query=아이폰15+리뷰"
    print("Fetching", search_url)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
        )
        page = await context.new_page()
        
        await page.goto(search_url, timeout=15000)
        await page.wait_for_selector('a[href*="blog.naver.com/"]', timeout=10000)
        
        # Extract link and any text around it that might indicate "Influencer"
        # The parent or grandparent usually contains the influencer badge.
        data = await page.evaluate('''() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="blog.naver.com/"]');
            for(let a of links) {
                // look for '인플루언서' text in the closest container
                const container = a.closest('.api_txt_lines') || a.closest('li') || a.parentElement;
                if(!container) continue;
                
                const text = container.innerText || "";
                const isInfluencer = text.includes('인플루언서');
                const isPopular = text.includes('인기글');
                
                // also check the user block
                const userBlock = container.querySelector('.user_info') || container.querySelector('.sub_name');
                const userText = userBlock ? userBlock.innerText : "";
                
                results.push({
                    href: a.href,
                    isInfluencer: isInfluencer || userText.includes('인플루언서'),
                    fullTextSnippet: text.substring(0, 100).replace(/\\n/g, ' ')
                });
            }
            return results;
        }''')
        
        print(json.dumps(data, indent=2, ensure_ascii=False))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_naver_search())
