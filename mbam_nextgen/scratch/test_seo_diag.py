import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def diagnostic():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    print("[DIAG] Initializing SeoAnalyzer...")
    analyzer = SeoAnalyzer()
    keyword = "부산동래맛집"
    
    # Force bypass cache by setting cache duration to 0 or removing it
    cache_path = analyzer._get_cache_path(keyword)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("[DIAG] Cleared cache.")
        
    print("[DIAG] Calling analyzer.analyze_keyword(keyword)...")
    
    # Let's perform step-by-step execution identical to analyze_keyword
    print("[DIAG] Step 1: Fetching top blogs and related keywords...")
    
    # 1. fetch_top_blogs
    print("[DIAG] -> Fetching top blogs...")
    try:
        blogs, smart_blocks = await analyzer.fetch_top_blogs(keyword)
        print(f"[DIAG] -> Top blogs fetched: {len(blogs)} blogs, {len(smart_blocks)} smart blocks")
        for idx, b in enumerate(blogs):
            print(f"   Blog {idx+1}: Title='{b.get('title')}', CharCount={b.get('char_count')}, ImgCount={b.get('img_count')}")
    except Exception as e:
        print("[DIAG] ERROR fetching top blogs:", e)
        return
        
    # 2. fetch_related_keywords
    print("[DIAG] -> Fetching related keywords...")
    try:
        related = await analyzer.fetch_related_keywords(keyword)
        print(f"[DIAG] -> Related keywords: {related}")
    except Exception as e:
        print("[DIAG] ERROR fetching related keywords:", e)
        related = []

    if not blogs:
        print("[DIAG] No blogs found, stopping.")
        return

    # 3. fetch_keyword_volumes
    print("[DIAG] Step 2: Fetching keyword volumes...")
    try:
        kw_volumes = await analyzer.fetch_keyword_volumes([keyword] + related[:4])
        print(f"[DIAG] -> Keyword volumes: {kw_volumes}")
    except Exception as e:
        print("[DIAG] ERROR fetching keyword volumes:", e)
        kw_volumes = []

    # 4. extract_keywords_with_ai
    print("[DIAG] Step 3: Extracting keywords with AI...")
    texts = [b['text'] for b in blogs]
    try:
        print(f"[DIAG] Calling extract_keywords_with_ai with {len(texts)} texts...")
        top_keywords = await analyzer.extract_keywords_with_ai(texts)
        print(f"[DIAG] -> Top keywords count: {len(top_keywords)}")
    except Exception as e:
        print("[DIAG] ERROR extracting keywords with AI:", e)
        top_keywords = []

    # 5. generate_winning_formula
    print("[DIAG] Step 4: Generating winning formula...")
    try:
        formula = await analyzer.generate_winning_formula(keyword, blogs, top_keywords)
        print(f"[DIAG] -> Formula: {formula[:100]}...")
    except Exception as e:
        print("[DIAG] ERROR generating winning formula:", e)
        formula = "Error generating formula"

    print("[DIAG] Done! Diagnostics complete.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(diagnostic())
