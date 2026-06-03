import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def diagnostic():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # Load env first
    load_dotenv("mbam_nextgen/.env")

    print("[DIAG] Initializing SeoAnalyzer...")
    analyzer = SeoAnalyzer()
    
    # Use sync client in a thread pool for _call_gemini to avoid async locks on large payloads
    # Let's override the _call_gemini method dynamically to test
    async def _call_gemini_optimized(prompt: str) -> str:
        print(f"[DIAG] Calling Gemini via thread pool (Prompt size: {len(prompt)})...")
        # Run sync generate_content in thread pool
        response = await asyncio.to_thread(
            analyzer.soul.gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text

    analyzer.soul._call_gemini = _call_gemini_optimized

    # Override extract_keywords_with_ai to use less text (top 5 blogs, 800 chars each)
    async def extract_keywords_with_ai_optimized(texts: list) -> list:
        print(f"[DIAG] Extracting keywords with AI for top {min(len(texts), 5)} blogs...")
        # Use top 5 blogs, first 800 characters each
        truncated_texts = [t[:800] for t in texts[:5]]
        combined_text = "\n---\n".join(truncated_texts)
        
        prompt = f"""
        당신은 완벽한 한국어 형태소 분석기입니다.
        아래의 텍스트 모음(상위 노출 블로그 본문들)을 분석하여, 가장 자주 사용된 핵심 명사(NNG, NNP) 20개를 추출하고 그 빈도수를 계산해 주세요.
        조사, 어미, 의미 없는 단어(예: 것, 수, 이, 저, 등)는 철저히 제외하고, 검색 최적화(SEO)에 유의미한 '핵심 서브 키워드'만 남겨야 합니다.
        
        응답은 반드시 아래 형식의 순수 JSON으로만 출력하세요:
        {{
          "top_keywords": [
            {{"keyword": "단어1", "count": 15}},
            {{"keyword": "단어2", "count": 12}}
          ]
        }}
        
        [텍스트 시작]
        {combined_text}
        [텍스트 끝]
        """
        try:
            response_text = await analyzer.soul._call_gemini(prompt)
            import re, json
            json_str = re.sub(r'```json\s*|```', '', response_text).strip()
            return json.loads(json_str).get("top_keywords", [])
        except Exception as e:
            print(f"[SEO] 키워드 추출 실패: {e}")
            return []

    analyzer.extract_keywords_with_ai = extract_keywords_with_ai_optimized

    keyword = "부산동래맛집"
    
    # Clear cache
    cache_path = analyzer._get_cache_path(keyword)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("[DIAG] Cleared cache.")
        
    print("[DIAG] Starting keyword analysis...")
    start_time = asyncio.get_event_loop().time()
    
    results = await analyzer.analyze_keyword(keyword)
    
    end_time = asyncio.get_event_loop().time()
    
    print("\n--- RESULTS ---")
    print("Keyword:", results.get("keyword"))
    print("Metrics collected:", len(results.get("metrics", [])))
    print("Top keywords extracted:", [k['keyword'] for k in results.get("top_keywords", [])[:5]])
    print("Winning Formula (first 100 chars):", results.get("formula", "")[:100].replace('\n', ' '))
    print(f"Total Time Taken: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(diagnostic())
