import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def get_blog_stats(blog_id):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    # Test mobile profile page
    url = f"https://m.blog.naver.com/BlogProfile.naver?blogId={blog_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            # Look for neighbor count
            # Often it's in a class like .count or .num
            texts = soup.get_text()
            print("Profile texts (first 500 chars):", texts.replace('\n', ' ')[:500])
            
            # Look specifically for today/total visitors
            # Naver PC sidebar usually has #ipcdi ...
            
            # Another endpoint: https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blogId}
            visitor_url = f"https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blog_id}"
            async with session.get(visitor_url, headers=headers) as v_resp:
                v_html = await v_resp.text()
                print("Visitor API:", v_html)

if __name__ == "__main__":
    if __import__("os").name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(get_blog_stats("sunmi282"))
