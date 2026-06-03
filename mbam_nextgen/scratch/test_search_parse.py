import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

async def main():
    keyword = "부산동래맛집"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/04.1"}
    search_url = f"https://m.search.naver.com/search.naver?where=m_blog&query={keyword}"
    
    print(f"Fetching {search_url}...")
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers, timeout=5) as resp:
            print("Status:", resp.status)
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                print("All a tags containing blog.naver.com:")
                count = 0
                for a in soup.select('a'):
                    href = a.get('href')
                    if not href: continue
                    if "blog.naver.com" in href:
                        count += 1
                        print(f"{count}: Href: {href}")
                        print(f"   Text: {a.get_text().strip()}")
                        match = re.search(r'(blog\.naver\.com/[^/]+/\d+)', href)
                        print(f"   Regex Match: {match.group(1) if match else 'None'}")

if __name__ == "__main__":
    import os
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
