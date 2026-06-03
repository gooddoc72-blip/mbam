import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # Load environment
    load_dotenv("mbam_nextgen/.env")

    print("[FINAL-TEST] Creating SeoAnalyzer...")
    analyzer = SeoAnalyzer()
    
    keyword = "부산동래맛집"
    
    # Clear cache to guarantee a fresh live request
    cache_path = analyzer._get_cache_path(keyword)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("[FINAL-TEST] Cleared cache.")

    print(f"[FINAL-TEST] Running analyze_keyword for '{keyword}'...")
    start_time = asyncio.get_event_loop().time()
    
    try:
        results = await analyzer.analyze_keyword(keyword)
        end_time = asyncio.get_event_loop().time()
        
        print("\n--- RESULTS ---")
        print("Success:", "error" not in results)
        print("Keyword:", results.get("keyword"))
        print("Metrics collected:", len(results.get("metrics", [])))
        if "metrics" in results and results["metrics"]:
            print("First Blog Title:", results["metrics"][0].get("title"))
            print("First Blog CharCount:", results["metrics"][0].get("char_count"))
            print("First Blog ImgCount:", results["metrics"][0].get("img_count"))
        print("Top keywords extracted count:", len(results.get("top_keywords", [])))
        print("Top 5 keywords:", [k['keyword'] for k in results.get("top_keywords", [])[:5]])
        print("Winning Formula Length:", len(results.get("formula", "")))
        print("Winning Formula Preview:")
        print(results.get("formula", "")[:300])
        print(f"Total Execution Time: {end_time - start_time:.2f} seconds")
    except Exception as e:
        print("Exception during final test:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
