import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import sys

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
        
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
                
                print("--- ALL blog.naver.com hrefs found in response ---")
                count = 0
                for a in soup.select('a'):
                    href = a.get('href')
                    if not href: continue
                    if "blog.naver.com" in href:
                        count += 1
                        text = a.get_text().strip().replace('\n', ' ')
                        print(f"[{count}] {href} | Text: {text}")
                        # Match both formats:
                        # 1. m.blog.naver.com/blog_id/log_no
                        # 2. blog.naver.com/PostView.naver?blogId=...&logNo=...
                        match1 = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', href)
                        match2 = re.search(r'blogId=([^&]+).*?logNo=(\d+)', href)
                        if match1:
                            print(f"    -> Standard Match: ID={match1.group(1)}, LogNo={match1.group(2)}")
                        elif match2:
                            print(f"    -> Query Match: ID={match2.group(1)}, LogNo={match2.group(2)}")
                        else:
                            print("    -> No match (likely Clip or Profile)")

if __name__ == "__main__":
    import os
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
