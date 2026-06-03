import aiohttp
import asyncio
from bs4 import BeautifulSoup

async def test_search():
    url = "https://search.naver.com/search.naver?where=view&query=전포동+맛집"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            
            items = soup.select("li.bx")
            print(f"Found {len(items)} bx items")
            
            for idx, item in enumerate(items[:10]):
                text = item.get_text()
                is_influencer = "인플루언서" in text
                is_popular = "인기글" in text or "인기주제" in text
                
                a_tag = item.select_one("a.title_link")
                href = a_tag.get("href") if a_tag else "No link"
                title = a_tag.get_text() if a_tag else "No title"
                
                print(f"[{idx+1}] Influencer:{is_influencer}, Popular:{is_popular} | {title} | {href}")

if __name__ == "__main__":
    if __import__("os").name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search())
