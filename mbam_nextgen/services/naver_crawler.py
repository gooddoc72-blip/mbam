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
            page = browser.new_page(user_agent=USER_AGENT)
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
                "source": "dom_crawler"
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

def fetch_place_coords(mid):
    """매장(MID)의 실제 좌표(위경도)를 추출한다.
    플레이스 순위는 검색자 위치 기반으로 개인화되므로, 로컬 순위 측정 시
    더미 좌표가 아닌 '대상 매장 위치'를 기준점으로 써야 정확하다.
    상세 페이지(__APOLLO_STATE__/og:image)에 좌표가 들어있어 외부 지오코딩이 불필요하다.
    반환: {"success":bool, "x":lng, "y":lat, "gps":"lat,lng", "address":str}
    """
    # 카테고리별로 경로 세그먼트가 다름(restaurant/hospital/place 등) → 여러 후보 시도
    kinds = ["restaurant", "place", "hospital", "hairshop", "beauty", "attraction"]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            try:
                for kind in kinds:
                    try:
                        page.goto(f"https://pcmap.place.naver.com/{kind}/{mid}/home", wait_until="domcontentloaded", timeout=12000)
                        page.wait_for_timeout(1500)
                        html = page.content()
                    except Exception:
                        continue
                    m = (re.search(r'"coordinate":\{[^}]*?"x":"?([\d.]+)"?[^}]*?"y":"?([\d.]+)"?', html)
                         or re.search(r'"x":"(1[0-9]{2}\.\d+)","y":"(3[0-9]\.\d+)"', html)
                         or re.search(r'center=([\d.]+)%2C([\d.]+)', html)
                         or re.search(r'center=([\d.]+),([\d.]+)', html))
                    if m:
                        lng, lat = float(m.group(1)), float(m.group(2))
                        # 한국 좌표 sanity check (경도 124~132, 위도 33~43)
                        if not (124 <= lng <= 132 and 33 <= lat <= 43):
                            continue
                        addr_m = re.search(r'"(?:roadAddress|address)":"([^"]{4,60})"', html)
                        return {
                            "success": True,
                            "mid": str(mid),
                            "x": lng,
                            "y": lat,
                            "gps": f"{lat},{lng}",
                            "address": addr_m.group(1) if addr_m else "",
                        }
                return {"success": False, "mid": str(mid), "error": "좌표를 찾지 못했습니다."}
            finally:
                browser.close()
    except Exception as e:
        return {"success": False, "mid": str(mid), "error": str(e)}


def search_keyword_ranking(keyword, limit=300, gps=None, proxy=None):
    """
    네이버 플레이스 '자연 순위' 수집기.
    - DOM 스크롤 파싱(불안정) 전면 폐기.
    - 검색결과 list API(restaurant/list · place/list · hairshop/list 등)의
      window.__APOLLO_STATE__ 안에서 '가장 큰 placeList'(=진짜 검색결과)만 순서대로 파싱.
    - 작은 placeList(새로오픈 추천 등 '가짜' 리스트)는 무시.
    - start 파라미터로 페이지네이션하여 limit까지 수집.
    """
    import urllib.parse

    def _extract_apollo(html):
        """__APOLLO_STATE__ 객체를 균형 중괄호로 정확히 추출."""
        idx = html.find("__APOLLO_STATE__")
        if idx < 0:
            return None
        j = html.find("{", idx)
        if j < 0:
            return None
        depth = 0; instr = False; esc = False
        for k in range(j, len(html)):
            c = html[k]
            if instr:
                if esc: esc = False
                elif c == "\\": esc = True
                elif c == '"': instr = False
            else:
                if c == '"': instr = True
                elif c == "{": depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(html[j:k + 1])
                        except Exception:
                            return None
        return None

    def _largest_placelist(data):
        """ROOT_QUERY 안에서 가장 큰 placeList(진짜 검색결과)의 items를 반환."""
        rq = data.get("ROOT_QUERY", {})
        best = []
        for kk, v in rq.items():
            if kk.startswith("placeList") and isinstance(v, dict) and isinstance(v.get("businesses"), dict):
                items = v["businesses"].get("items", [])
                if len(items) > len(best):
                    best = items
        return best

    def _int(v):
        d = re.sub(r"[^0-9]", "", str(v or ""))
        return int(d) if d else 0

    try:
        with sync_playwright() as p:
            launch_args = {"headless": True}
            if proxy:
                launch_args["proxy"] = {"server": proxy}
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            # 본문(document)·xhr·script는 통과(필요), 무거운 리소스만 차단
            context.route("**/*", lambda r: r.abort() if r.request.resource_type in ["image", "media", "font", "stylesheet"] else r.continue_())
            page = context.new_page()

            # 1) 지도 검색으로 세션 워밍업 + 실제 list API URL(엔드포인트 타입/좌표/파라미터) 캡처
            list_url = {"u": None}

            def on_resp(r):
                try:
                    if re.search(r"pcmap\.place\.naver\.com/[a-z]+/list", r.url) and r.status == 200 and list_url["u"] is None:
                        list_url["u"] = r.url
                except Exception:
                    pass

            page.on("response", on_resp)
            page.goto(f"https://map.naver.com/p/search/{urllib.parse.quote(keyword)}", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            base = list_url["u"] or (
                f"https://pcmap.place.naver.com/place/list?query={urllib.parse.quote(keyword)}&display=70&start=1&locale=ko"
            )

            # gps(좌표) 주입 → 거리 기준점(매장 인근). 한국 좌표는 경도(>124) > 위도(<43)로 자동 판별.
            if gps:
                try:
                    a, b = [float(x) for x in re.split(r"[ ,;]+", gps.strip())[:2]]
                    lng, lat = (max(a, b), min(a, b))
                    for kx in ["x", "clientX"]:
                        base = re.sub(r"([?&]" + kx + r"=)[^&]*", r"\g<1>" + str(lng), base)
                    for ky in ["y", "clientY"]:
                        base = re.sub(r"([?&]" + ky + r"=)[^&]*", r"\g<1>" + str(lat), base)
                except Exception:
                    pass

            results = []
            seen = set()
            per = 70

            def _save_bucket(saves):
                if saves > 50000: return f"{saves // 1000 * 1000:,}+"
                if saves > 1000:  return f"{saves // 100 * 100:,}+"
                return f"~{saves // 50 * 50}"

            # ── GraphQL 페이지네이션 (start 무시되는 SSR을 대체, 350+위 수집 가능) ──
            # 네이버 list UI의 페이지 버튼 클릭 시 'getRestaurantsPcmap' graphql POST가 나간다.
            # 그 요청 본문(현재 유효한 쿼리)을 캡처해 start=1,71,141…로 재생하여 깊이 수집한다.
            gql = {"body": None, "ref": None}

            def on_gql(req):
                try:
                    if "pcmap-api.place.naver.com/graphql" in req.url and req.method == "POST" and gql["body"] is None:
                        pd = req.post_data or ""
                        if "placeList" in pd or "getRestaurantsPcmap" in pd:
                            gql["body"] = pd
                            gql["ref"] = req.headers.get("referer")
                except Exception:
                    pass

            page.on("request", on_gql)

            # 결과 iframe에서 '2'(또는 다음페이지) 클릭 → 유효 쿼리 유발/캡처
            try:
                fr = None
                for f in page.frames:
                    if "pcmap.place.naver.com" in (f.url or "") and "list" in (f.url or ""):
                        fr = f; break
                if fr:
                    btn = fr.locator("a.mBN2s:has-text('2'), a:has-text('다음페이지')")
                    if btn.count() > 0:
                        btn.first.click(timeout=4000)
                        page.wait_for_timeout(2500)
            except Exception:
                pass

            # gps("lat,lng") → (x=lng, y=lat) 문자열
            gps_xy = None
            if gps:
                try:
                    a, b = [float(x) for x in re.split(r"[ ,;]+", gps.strip())[:2]]
                    gps_xy = (str(max(a, b)), str(min(a, b)))
                except Exception:
                    gps_xy = None

            if gql["body"]:
                try:
                    tmpl = json.loads(gql["body"])
                except Exception:
                    tmpl = None
                arr = tmpl if isinstance(tmpl, list) else ([tmpl] if tmpl else [])
                qobj = None
                for q in arr:
                    if isinstance(q, dict) and q.get("operationName") == "getRestaurantsPcmap":
                        qobj = q; break
                if qobj is None and arr:
                    qobj = arr[0]
                ref = gql["ref"] or "https://pcmap.place.naver.com/"

                if qobj:
                    for start in range(1, limit + 1, per):
                        body = json.loads(json.dumps(qobj))
                        inp = body.setdefault("variables", {}).setdefault("input", {})
                        inp["query"] = keyword
                        inp["start"] = start
                        inp["display"] = per
                        if gps_xy:
                            inp["x"], inp["y"] = gps_xy
                        try:
                            resp = page.request.post(
                                "https://pcmap-api.place.naver.com/graphql",
                                data=json.dumps([body]),
                                headers={"Content-Type": "application/json", "Referer": ref, "Origin": "https://pcmap.place.naver.com"},
                            )
                            d = json.loads(resp.text())
                        except Exception:
                            break
                        d0 = d[0] if isinstance(d, list) else d
                        items = []
                        for k, v in (d0.get("data") or {}).items():
                            if isinstance(v, dict) and isinstance(v.get("businesses"), dict):
                                items = v["businesses"].get("items") or []
                                break
                        if not items:
                            break
                        added = 0
                        for it in items:
                            pid = str(it.get("id") or "")
                            name = (it.get("name") or "").strip()
                            if not pid or not name or pid in seen:
                                continue
                            seen.add(pid)
                            cat = it.get("category") or ""
                            if isinstance(cat, list):
                                cat = cat[-1] if cat else ""
                            results.append({
                                "mid": pid, "name": name, "cat": cat,
                                "rec": _int(it.get("visitorReviewCount")), "rec_d": 0,
                                "blog": _int(it.get("blogCafeReviewCount")), "blog_d": 0,
                                "save": _save_bucket(_int(it.get("saveCount"))),
                                "is_new": bool(it.get("newOpening")) or ("새로오픈" in str(it.get("markerLabel") or "")),
                                "has_revisit": bool(it.get("repeatVisit")),
                            })
                            added += 1
                            if len(results) >= limit:
                                break
                        if added == 0 or len(results) >= limit:
                            break

            # ── 폴백: GraphQL 미캡처(결과 ≤70 등) 시 SSR 첫 페이지라도 파싱 ──
            if not results:
                try:
                    u = re.sub(r"([?&]display=)\d+", r"\g<1>" + str(per), base)
                    if "display=" not in u:
                        u += f"&display={per}"
                    page.goto(u, wait_until="domcontentloaded")
                    data = _extract_apollo(page.content())
                    items = _largest_placelist(data) if data else []
                    for it in items:
                        ref0 = it.get("__ref", "") if isinstance(it, dict) else ""
                        d = data.get(ref0, {}) if ref0 else {}
                        name = (d.get("name") or "").strip()
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        cat = d.get("category") or ""
                        if isinstance(cat, list):
                            cat = cat[-1] if cat else ""
                        results.append({
                            "mid": str(d.get("id") or (ref0.split(":")[-1] if ":" in ref0 else ref0) or "0"),
                            "name": name, "cat": cat,
                            "rec": _int(d.get("visitorReviewCount")), "rec_d": 0,
                            "blog": _int(d.get("blogCafeReviewCount")), "blog_d": 0,
                            "save": _save_bucket(_int(d.get("saveCount"))),
                            "is_new": bool(d.get("newOpening")) or ("새로오픈" in str(d.get("markerLabel") or "")),
                            "has_revisit": bool(d.get("repeatVisit")),
                        })
                        if len(results) >= limit:
                            break
                except Exception:
                    pass

            browser.close()
            return results[:limit]
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "detail":
        res = fetch_place_by_mid(sys.argv[2])
        print(json.dumps(res))
    elif len(sys.argv) >= 3 and sys.argv[1] == "coords":
        res = fetch_place_coords(sys.argv[2])
        print(json.dumps(res))
    elif len(sys.argv) >= 3 and sys.argv[1] == "search":
        keyword = sys.argv[2]
        limit = 300
        gps = None
        proxy = None
        
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i+1])
                i += 2
            elif sys.argv[i] == "--gps" and i + 1 < len(sys.argv):
                gps = sys.argv[i+1]
                i += 2
            elif sys.argv[i] == "--proxy" and i + 1 < len(sys.argv):
                proxy = sys.argv[i+1]
                i += 2
            else:
                try:
                    limit = int(sys.argv[i])
                except ValueError:
                    pass
                i += 1
                
        res = search_keyword_ranking(keyword, limit, gps=gps, proxy=proxy)
        print(json.dumps(res))
