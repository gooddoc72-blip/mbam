import asyncio
import sys
import json
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    analyzer = SeoAnalyzer()
    keyword = "부산동래맛집"
    
    # Clear cache first to force a fresh run
    cache_path = analyzer._get_cache_path(keyword)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("Cleared cache.")
        
    print(f"Testing analyze_keyword for '{keyword}'...")
    try:
        results = await analyzer.analyze_keyword(keyword)
        print("Success!")
        # Print a summarized version of the results
        summary = {
            "keyword": results.get("keyword"),
            "metrics_count": len(results.get("metrics", [])),
            "top_keywords_count": len(results.get("top_keywords", [])),
            "formula_length": len(results.get("formula", "")),
            "related_count": len(results.get("related", [])),
            "smart_blocks_count": len(results.get("smart_blocks", [])),
            "kw_volumes_count": len(results.get("kw_volumes", [])),
            "error": results.get("error")
        }
        print("Summary:", json.dumps(summary, ensure_ascii=False, indent=2))
        if "error" in results:
            print("Returned Error:", results["error"])
        else:
            print("Formula preview:", results.get("formula", "")[:200])
    except Exception as e:
        print("Exception occurred during analyze_keyword:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
