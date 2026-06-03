import asyncio
import aiohttp
import re
import json

async def get_blog_stats(blog_id):
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15"}
    url = f"https://m.blog.naver.com/{blog_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            match = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*?\});', html)
            if match:
                data = json.loads(match.group(1))
                try:
                    # Depending on the structure...
                    user_info = data['props']['pageProps']['initialState']['user']['userInfo']
                    # Let's print out what we can find
                    print("User Info keys:", user_info.keys())
                    print("subscriberCount (Neighbors):", user_info.get('subscriberCount'))
                    print("visitorCount (Total):", user_info.get('visitorCount'))
                    print("todayVisitorCount:", user_info.get('todayVisitorCount'))
                except Exception as e:
                    print("Error parsing json:", e)
                    # Dump a sample to see where it might be
                    print(str(data)[:1000])
            else:
                print("No NEXT_DATA found")

if __name__ == "__main__":
    if __import__("os").name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(get_blog_stats("sunmi282"))
