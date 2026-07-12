"""맛집 포스팅 소재 수집 — 플레이스 방문자 리뷰 + 블로그 후기를 모아 원고 소재(source_data)로 만든다.

- 플레이스 방문자 리뷰: httpx 로 수집(브라우저 불필요) → 클라우드 서버에서도 가능.
- 블로그 후기:
    · 클라우드 서버(browser_ok=False): 네이버 공식 블로그 검색 API(httpx, 브라우저 불필요).
    · 로컬 에이전트(browser_ok=True): playwright 로 본문까지 수집(더 풍부).
- 원고 주제가 정확하도록 '가게 이름'을 소스 최상단에 넣는다.
"""


async def _naver_blog_search(query: str, display: int = 5) -> list:
    """네이버 공식 블로그 검색 API(데이터센터 IP 가능, 브라우저 불필요). 스니펫만 반환."""
    import os
    import re
    import html as _html
    import httpx
    cid = os.getenv("NAVER_CLIENT_ID")
    csec = os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and csec and query):
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://openapi.naver.com/v1/search/blog.json",
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
                params={"query": query, "display": display, "sort": "sim"},
                timeout=10.0,
            )
        if r.status_code != 200:
            return []
        items = r.json().get("items", [])
    except Exception:
        return []

    def _clean(s):
        return _html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

    return [{"title": _clean(it.get("title")), "desc": _clean(it.get("description")), "link": it.get("link", "")} for it in items]


async def _fetch_naver_blog_body(link: str, client) -> str:
    """네이버 블로그 본문을 httpx 로 가져와 텍스트만 추출(브라우저 불필요). 실패 시 ''.
    블로그 글은 iframe(mainFrame) 안에 있어 PostView URL 로 정규화 후 파싱한다."""
    if not link:
        return ""
    try:
        import re
        from bs4 import BeautifulSoup
        m = re.search(r"blog\.naver\.com/([^/?]+)/(\d+)", link) or re.search(r"blogId=([^&]+).*?logNo=(\d+)", link)
        view = (f"https://blog.naver.com/PostView.naver?blogId={m.group(1)}&logNo={m.group(2)}"
                if m else link)
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
        r = await client.get(view, headers=ua, timeout=8.0, follow_redirects=True)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        node = (soup.select_one(".se-main-container")      # 스마트에디터 ONE
                or soup.select_one("#postViewArea")         # 구 에디터
                or soup.select_one(".post-view")
                or soup.select_one("#viewTypeSelector"))
        if not node:
            return ""
        text = node.get_text("\n", strip=True)
        text = re.sub(r"\n{2,}", "\n", text).strip()
        return text[:1500]
    except Exception:
        return ""


async def collect_matjip_source(place_url: str = "", keyword: str = "", log=None, browser_ok: bool = True) -> dict:
    """맛집 소재 수집. browser_ok=False(클라우드)는 브라우저 없이(httpx+공식API) 수집한다."""
    place_url = (place_url or "").strip()
    keyword = (keyword or "").strip()

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass
        print(f"[matjip] {msg}")

    parts = []
    place_name = ""

    # 1) 플레이스 방문자 리뷰 (httpx)
    if place_url:
        try:
            _log("플레이스 방문자 리뷰 수집 중...")
            from mbam_nextgen.services.place_review_service import PlaceReviewService
            d = await PlaceReviewService().collect_reviews(place_url)
            place_name = (d.get("place_name") or "").strip()
            texts = []
            for r in (d.get("reviews") or [])[:25]:
                t = r if isinstance(r, str) else (r.get("text") or r.get("content") or r.get("review") or "")
                if t and str(t).strip():
                    texts.append(f"- {str(t).strip()}")
            if texts:
                parts.append("[방문자 리뷰]\n" + "\n".join(texts))
                _log(f"'{place_name or '가게'}' 방문자 리뷰 {len(texts)}건 수집")
        except Exception as e:
            _log(f"플레이스 리뷰 수집 실패(계속): {e}")

    # 2) 블로그 후기 — 검색어는 가게 이름 우선(정확), 없으면 입력 키워드
    blog_query = place_name or keyword
    if blog_query:
        if browser_ok:
            # 로컬 에이전트: playwright 로 본문까지 수집(풍부)
            try:
                _log(f"'{blog_query}' 블로그 후기 수집 중...(에이전트)")
                from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
                results, _sb = await SeoAnalyzer().fetch_top_blogs(blog_query, limit=5)
                n = 0
                for it in (results or [])[:5]:
                    c = (it.get("content") or "")[:1200]
                    if c.strip():
                        parts.append(f"[블로그 후기: {it.get('title', '')}]\n{c.strip()}")
                        n += 1
                _log(f"블로그 후기 {n}건 수집")
            except Exception as e:
                _log(f"블로그 후기 수집 실패(계속): {e}")
        else:
            # 클라우드 서버: 공식 API로 링크 확보 → 각 글 본문을 httpx로 파싱(브라우저 불필요)
            try:
                _log(f"'{blog_query}' 블로그 후기(공식 검색+본문) 수집 중...")
                items = await _naver_blog_search(blog_query, display=6)
                import httpx as _httpx
                n = 0
                async with _httpx.AsyncClient() as _bc:
                    for it in items:
                        if n >= 4:
                            break
                        body = await _fetch_naver_blog_body(it.get("link", ""), _bc)
                        text = (body or (it.get("desc") or "")).strip()  # 본문 실패 시 요약 폴백
                        if text:
                            parts.append(f"[블로그 후기: {it.get('title', '')}]\n{text}")
                            n += 1
                _log(f"블로그 후기(공식) {n}건 수집(본문 우선)")
            except Exception as e:
                _log(f"블로그 후기(공식) 수집 실패(계속): {e}")

    if not parts:
        raise RuntimeError("참고 소재를 수집하지 못했습니다. 플레이스 URL 또는 키워드를 확인하세요.")

    # 가게 이름을 소스 최상단에 넣어 원고 주제가 정확하도록 한다.
    if place_name:
        parts.insert(0, f"[가게 이름] {place_name}")

    source = "\n\n".join(parts).strip()
    return {"success": True, "source_data": source, "place_name": place_name}
