import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def fetch_post(blog_id, log_no):
    url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            content = soup.select_one('.se-main-container, #postViewArea')
            if content:
                print(f"Success! Char count: {len(content.get_text(strip=True))}")
            else:
                print("Failed to find content.")

if __name__ == "__main__":
    if __import__("os").name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(fetch_post("sunmi282", "224218455486"))
