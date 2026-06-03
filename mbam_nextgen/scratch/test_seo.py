import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def main():
    analyzer = SeoAnalyzer()
    keyword = "동래맛집"
    print(f"Testing fetch_top_blogs for '{keyword}'...")
    results = await analyzer.fetch_top_blogs(keyword)
    print(f"Results length: {len(results)}")
    if results:
        for r in results:
            print(r['url'], r['char_count'], r['img_count'])
    else:
        print("No results found.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
