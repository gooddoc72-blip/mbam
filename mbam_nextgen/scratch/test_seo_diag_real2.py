import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env first before imports to ensure keys are loaded immediately
load_dotenv("mbam_nextgen/.env")

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    print("[DIAG] Instantiating live SeoAnalyzer...")
    analyzer = SeoAnalyzer()
    keyword = "부산동래맛집"
    
    # Force bypass cache
    cache_path = analyzer._get_cache_path(keyword)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("[DIAG] Cleared cache.")

    print(f"[DIAG] Calling analyzer.analyze_keyword('{keyword}')...")
    
    # Let's perform step by step tracing of the actual live methods
    # 1. fetch_top_blogs
    blogs, smart_blocks = await analyzer.fetch_top_blogs(keyword)
    print(f"[DIAG] Top blogs: {len(blogs)}")
    
    # 2. extract_keywords_with_ai
    texts = [b['text'] for b in blogs]
    print(f"[DIAG] Calling extract_keywords_with_ai with {len(texts)} blogs...")
    
    # Let's add some print logging inside analyzer.soul._call_gemini dynamically just to see prompt/response
    original_call = analyzer.soul._call_gemini
    async def logged_call(prompt):
        print(f"[DIAG] -> _call_gemini called with prompt size: {len(prompt)}")
        try:
            res = await original_call(prompt)
            print(f"[DIAG] -> _call_gemini returned response size: {len(res)}")
            return res
        except Exception as ex:
            print(f"[DIAG] -> _call_gemini FAILED: {ex}")
            raise ex
            
    analyzer.soul._call_gemini = logged_call
    
    print("[DIAG] Tracing AI keyword extraction...")
    top_kws = await analyzer.extract_keywords_with_ai(texts)
    print(f"[DIAG] Keywords extracted: {len(top_kws)}")
    
    print("[DIAG] Tracing AI formula generation...")
    formula = await analyzer.generate_winning_formula(keyword, blogs, top_kws)
    print(f"[DIAG] Formula generated size: {len(formula)}")
    
    print("[DIAG] Done!")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
