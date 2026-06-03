import asyncio, aiohttp, re
async def test():
    async with aiohttp.ClientSession() as s:
        async with s.get('https://cafe.naver.com/cjyeonsu') as r:
            html = await r.text()
            match = re.search(r'clubid=(\d+)', html.lower()) or re.search(r'g_sclubid\s*=\s*[\"\']?(\d+)', html.lower())
            print('CID:', match.group(1) if match else None)
asyncio.run(test())
