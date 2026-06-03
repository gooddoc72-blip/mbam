"""
fetch_cafe_author_info() + analyze_multiple_urls() 통합 검증.
- 2026-05-26 추가된 cafe_author_info 트랙이 양쪽 카페 글에서 정상 추출되는지 확인.
- text_type/source가 '네이버 카페' 로 분기되는지 확인.
- blog_info가 더 이상 잘못 호출되지 않는지 확인.
"""
import asyncio
import json
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

URLS = [
    "https://cafe.naver.com/ungsangjang/828892",
    "https://cafe.naver.com/mindy7857/5182039",
]


async def main():
    a = SeoAnalyzer()
    results = await a.analyze_multiple_urls(URLS)
    for url, detail in results.items():
        print(f"\n===== {url} =====")
        if "error" in detail:
            print("  ERROR:", detail["error"])
            continue
        print(f"  text_type:   {detail.get('text_type')}")
        print(f"  source:      {detail.get('source')}")
        print(f"  blog_id:     {detail.get('blog_id')}")
        print(f"  blog_info:   {detail.get('blog_info')}  (카페면 비어있어야 정상)")
        print(f"  title:       {detail.get('title')}")
        print(f"  char_count:  {detail.get('char_count')}")
        print(f"  img_count:   {detail.get('img_count')}")
        cai = detail.get("cafe_author_info") or {}
        print(f"  cafe_author_info:")
        print(json.dumps(cai, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    asyncio.run(main())
