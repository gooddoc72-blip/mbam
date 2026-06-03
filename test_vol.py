import asyncio
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def test():
    analyzer = SeoAnalyzer()
    res = await analyzer.fetch_keyword_volumes(['광안리 맛집'])
    print(res)

if __name__ == '__main__':
    asyncio.run(test())
