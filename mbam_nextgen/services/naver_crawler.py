import sys
import json
import re
import random
import time
from playwright.sync_api import sync_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch_place_by_mid(mid):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://pcmap.place.naver.com/restaurant/{mid}/home", wait_until="networkidle")
            
            title = page.locator("meta[property='og:title']").get_attribute("content")
            if not title:
                title = f"플레이스 매장 ({mid})"
            else:
                title = title.split(" : ")[0].strip() if " : " in title else title
                
            visitor_reviews = 0
            blog_reviews = 0
            try:
                page.wait_for_timeout(3000)
                html = page.content()
                import re
                v_matches = re.findall(r'방문자리뷰[^\d]*([\d,]+)', html)
                if v_matches:
                    visitor_reviews = max([int(m.replace(',', '')) for m in v_matches])
                
                b_matches = re.findall(r'블로그리뷰[^\d]*([\d,]+)', html)
                if b_matches:
                    blog_reviews = max([int(m.replace(',', '')) for m in b_matches])
            except:
                pass
                
            browser.close()
            
            return {
                "success": True,
                "mid": mid,
                "name": title,
                "category": "음식점",
                "visitor_reviews": visitor_reviews,
                "blog_reviews": blog_reviews,
                "has_booking": True,
                "source": "api_interception"
            }
    except Exception as e:
        return {
            "success": False,
            "mid": mid,
            "name": f"플레이스 매장 ({mid})",
            "category": "음식점",
            "visitor_reviews": 0,
            "blog_reviews": 0,
            "has_booking": True,
            "source": "error"
        }

def search_keyword_ranking(keyword, limit=300):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            
            results = []
            seen_mids = set()
            
            def handle_response(response):
                try:
                    url = response.url
                    if "api/search/allSearch" in url and response.status == 200:
                        data = response.json()
                        places = data.get("result", {}).get("place", {}).get("list", [])
                    elif "pcmap-api.place.naver.com/graphql" in url and response.status == 200:
                        data = response.json()
                        if isinstance(data, list):
                            data = data[0]
                        d_data = data.get("data", {})
                        places = []
                        for k, v in d_data.items():
                            if isinstance(v, dict) and "businesses" in v:
                                places.extend(v["businesses"].get("items", []))
                    elif ("restaurant/list" in url or "place/list" in url) and response.status == 200:
                        import re
                        html = response.text()
                        match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});\s*window\.', html, re.DOTALL)
                        places = []
                        if match:
                            data = json.loads(match.group(1))
                            rq = data.get("ROOT_QUERY", {})
                            target_refs = []
                            max_len = 0
                            for k, v in rq.items():
                                if k.startswith("placeList") and isinstance(v, dict) and "businesses" in v:
                                    items = v["businesses"].get("items", [])
                                    if len(items) > max_len:
                                        max_len = len(items)
                                        target_refs = items
                            
                            for ref_obj in target_refs:
                                ref_key = ref_obj.get("__ref", "")
                                if ref_key and ref_key in data:
                                    item_data = data[ref_key]
                                    if isinstance(item_data, dict) and "name" in item_data and "id" in item_data:
                                        places.append(item_data)
                    else:
                        return
                        
                    for p_data in places:
                        p_data = p_data.get("item", p_data) # GraphQL Wrapping 방어
                        mid = p_data.get("id") or p_data.get("apolloCacheId")
                        if mid and mid not in seen_mids:
                            seen_mids.add(mid)
                            name = p_data.get("name", "")
                            if name.startswith("예약"):
                                name = name.replace("예약", "", 1).strip()
                            
                            p_json_str = json.dumps(p_data, ensure_ascii=False)
                            is_new = p_data.get("isNew") or p_data.get("newOpen") or ("새로오픈" in name) or ("신규" in name) or ("새로오픈" in p_json_str)
                            has_revisit = "재방문 많은" in p_json_str or "재방문율" in p_json_str
                            
                            category = p_data.get("category", "")
                            if category and isinstance(category, list):
                                category = category[-1] if len(category) > 0 else "음식점"
                                
                            import re
                            # Robustly parse numbers
                            v_rev = p_data.get("placeReviewCount") or p_data.get("visitorReviewScore") or p_data.get("visitorReviewCount") or 0
                            visitor_reviews = int(re.sub(r'[^0-9]', '', str(v_rev))) if re.sub(r'[^0-9]', '', str(v_rev)) else 0
                            
                            b_rev = p_data.get("blogCafeReviewCount") or p_data.get("reviewCount") or 0
                            blog_reviews = int(re.sub(r'[^0-9]', '', str(b_rev))) if re.sub(r'[^0-9]', '', str(b_rev)) else 0
                            
                            saves_raw = p_data.get("saveCount") or 0
                            saves = int(re.sub(r'[^0-9]', '', str(saves_raw))) if re.sub(r'[^0-9]', '', str(saves_raw)) else 0
                            
                            # mock changes for ui display
                            rec_d = random.choice([2, 5, 8, 12, 18, 25, 45, 110]) if len(results) % 2 == 0 else random.choice([-2, -5, -8, -12, -25])
                            blog_d = random.choice([1, 2, 4, 9, 15, 21, 41]) if len(results) % 2 == 0 else random.choice([-1, -3, -7])
                            
                            if saves > 50000:
                                save_str = f"{saves // 1000 * 1000:,}+"
                            elif saves > 1000:
                                save_str = f"{saves // 100 * 100:,}+"
                            else:
                                save_str = f"~{saves // 50 * 50}"
                            
                            results.append({
                                "mid": str(mid),
                                "name": name,
                                "cat": category,
                                "rec": visitor_reviews,
                                "rec_d": rec_d,
                                "blog": blog_reviews,
                                "blog_d": blog_d,
                                "save": save_str,
                                "is_new": is_new,
                            })
                except Exception as e:
                    pass
            page.on("response", handle_response)
            
            # 1. Load Naver Map to get cookies and context
            page.goto(f"https://map.naver.com/p/search/{keyword}", wait_until="networkidle")
            
            try:
                page.wait_for_selector("#searchIframe", timeout=15000)
                iframe = page.frame_locator("#searchIframe")
                iframe.locator(".place_bluelink, .UEzoS").first.wait_for(timeout=15000)
                
                # 1.5 Scroll on page 1 to trigger lazy loading of ranks 21-50
                for _ in range(4):
                    try:
                        iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)", timeout=5000)
                    except:
                        pass
                    page.wait_for_timeout(500)
            except Exception as e:
                pass
                
            page.wait_for_timeout(2000)
            
            # 2. Iterate pages 2 to 6 to collect up to 300
            for i in range(2, 7):
                if len(results) >= limit:
                    break
                
                try:
                    iframe = page.frame_locator("#searchIframe")
                    for _ in range(4):
                        try:
                            iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)", timeout=5000)
                        except:
                            pass
                        page.wait_for_timeout(500)
                        
                    try:
                        btn = iframe.locator("a.mBN2s").get_by_text(str(i), exact=True)
                        if btn.count() > 0:
                            btn.first.click(timeout=3000)
                        else:
                            raise Exception("No mBN2s exact text match")
                    except Exception as e1:
                        try:
                            iframe.locator(f".zRM9F a:has-text('{i}')").first.click(timeout=3000)
                        except Exception as e2:
                            iframe.locator(f"a:has-text('{i}')").last.click(timeout=3000)
                            
                    page.wait_for_timeout(2500)
                except Exception as e:
                    break # No more pages
                        
            browser.close()
            return results[:limit]
            
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Invalid arguments"}))
        sys.exit(1)
        
    cmd = sys.argv[1]
    arg = sys.argv[2]
    
    if cmd == "detail":
        res = fetch_place_by_mid(arg)
        print(json.dumps(res))
    elif cmd == "search":
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        '--window-position=-32000,-32000',
                        '--disable-blink-features=AutomationControlled',
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                # Block heavy resources to speed up crawling
                context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
                
                page = context.new_page()
                
                results = []
                seen_mids = set()
                
                def handle_response(response):
                    try:
                        url = response.url
                        if "api/search/allSearch" in url and response.status == 200:
                            data = response.json()
                            places = data.get("result", {}).get("place", {}).get("list", [])
                        elif "pcmap-api.place.naver.com/graphql" in url and response.status == 200:
                            data = response.json()
                            if isinstance(data, list):
                                data = data[0]
                            d_data = data.get("data", {})
                            places = []
                            for k, v in d_data.items():
                                if isinstance(v, dict) and "businesses" in v:
                                    places.extend(v["businesses"].get("items", []))
                        elif ("restaurant/list" in url or "place/list" in url) and response.status == 200:
                            import re
                            html = response.text()
                            match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});\s*window\.', html, re.DOTALL)
                            places = []
                            if match:
                                data = json.loads(match.group(1))
                                rq = data.get("ROOT_QUERY", {})
                                target_refs = []
                                max_len = 0
                                for k, v in rq.items():
                                    if k.startswith("placeList") and isinstance(v, dict) and "businesses" in v:
                                        items = v["businesses"].get("items", [])
                                        if len(items) > max_len:
                                            max_len = len(items)
                                            target_refs = items
                                
                                for ref_obj in target_refs:
                                    ref_key = ref_obj.get("__ref", "")
                                    if ref_key and ref_key in data:
                                        item_data = data[ref_key]
                                        if isinstance(item_data, dict) and "name" in item_data and "id" in item_data:
                                            places.append(item_data)
                        else:
                            return
                            
                        import re
                        for p_data in places:
                            p_data = p_data.get("item", p_data) # GraphQL Wrapping 방어
                            mid = p_data.get("id") or p_data.get("apolloCacheId")
                            if mid and mid not in seen_mids:
                                seen_mids.add(mid)
                                name = p_data.get("name", "")
                                if name.startswith("예약"):
                                    name = name.replace("예약", "", 1).strip()
                                
                                p_json_str = json.dumps(p_data, ensure_ascii=False)
                                is_new = p_data.get("isNew") or p_data.get("newOpen") or ("새로오픈" in name) or ("신규" in name) or ("새로오픈" in p_json_str)
                                has_revisit = "재방문 많은" in p_json_str or "재방문율" in p_json_str
                                
                                category = p_data.get("category", "")
                                if category and isinstance(category, list):
                                    category = category[-1] if len(category) > 0 else "음식점"
                                    
                                # Robustly parse numbers
                                v_rev = p_data.get("placeReviewCount") or p_data.get("visitorReviewScore") or p_data.get("visitorReviewCount") or 0
                                v_rev = int(re.sub(r'[^0-9]', '', str(v_rev))) if re.sub(r'[^0-9]', '', str(v_rev)) else 0
                                    
                                b_rev = p_data.get("blogCafeReviewCount") or p_data.get("reviewCount") or 0
                                b_rev = int(re.sub(r'[^0-9]', '', str(b_rev))) if re.sub(r'[^0-9]', '', str(b_rev)) else 0
                                    
                                saves = p_data.get("saveCount") or 0
                                saves = int(re.sub(r'[^0-9]', '', str(saves))) if re.sub(r'[^0-9]', '', str(saves)) else 0
                                
                                rec_d = random.choice([2, 5, 8, 12, 18, 25, 45, 110]) if len(results) % 2 == 0 else random.choice([-2, -5, -8, -12, -25])
                                blog_d = random.choice([1, 2, 4, 9, 15, 21, 41]) if len(results) % 2 == 0 else random.choice([-1, -3, -7])
                                
                                if saves > 50000:
                                    save_str = f"{saves // 1000 * 1000:,}+"
                                elif saves > 1000:
                                    save_str = f"{saves // 100 * 100:,}+"
                                else:
                                    save_str = f"~{saves // 50 * 50}"
                                
                                results.append({
                                    "mid": str(mid),
                                    "name": name,
                                    "cat": category,
                                    "rec": v_rev,
                                    "rec_d": rec_d,
                                    "blog": b_rev,
                                    "blog_d": blog_d,
                                    "save": save_str,
                                    "is_new": is_new,
                                })
                    except Exception as e:
                        pass
                            
                page.on("response", handle_response)
                
                # 1. Load Naver Map
                page.goto(f"https://map.naver.com/p/search/{arg}", wait_until="domcontentloaded")
                
                try:
                    page.wait_for_selector("#searchIframe", timeout=15000)
                    iframe = page.frame_locator("#searchIframe")
                    iframe.locator(".place_bluelink, .UEzoS").first.wait_for(timeout=15000)
                except Exception as e:
                    pass
                
                # 2. Iterate pages 2 to 6 to collect up to 300
                for i in range(2, 7):
                    if len(results) >= limit:
                        break
                    
                    try:
                        iframe = page.frame_locator("#searchIframe")
                        
                        # Scroll the exact scroll container to the bottom multiple times
                        for _ in range(4):
                            try:
                                iframe.locator("#_pcmap_list_scroll_container").evaluate("el => el.scrollTo(0, el.scrollHeight)", timeout=5000)
                            except:
                                pass
                            page.wait_for_timeout(500)
                        
                        if i <= 5:
                            # Try to click the specific page number
                            try:
                                btn = iframe.locator("a.mBN2s").get_by_text(str(i), exact=True)
                                if btn.count() > 0:
                                    btn.first.click(timeout=3000)
                                    clicked = True
                                else:
                                    clicked = False
                            except:
                                clicked = False
                        else:
                            # We need to click the 'Next' button
                            try:
                                # Naver Map pagination next button is usually the last anchor tag in the pagination container
                                iframe.locator(".zRM9F > a:last-child, .O8qbU > a:last-child, .pagination > a:last-child").last.click(timeout=3000)
                                clicked = True
                            except:
                                try:
                                    # Fallback: find any 'a' with '다음'
                                    iframe.locator("a:has-text('다음')").last.click(timeout=3000)
                                    clicked = True
                                except:
                                    clicked = False
                        
                        if clicked:
                            page.wait_for_timeout(800) # Reduced extremely to avoid proxy timeouts
                        else:
                            break
                    except Exception as e:
                        break
                            
                browser.close()
                print(json.dumps(results[:limit]))
                
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "search":
        search_keyword_ranking(sys.argv[2], int(sys.argv[3]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "detail":
        fetch_place_by_mid(sys.argv[2])
