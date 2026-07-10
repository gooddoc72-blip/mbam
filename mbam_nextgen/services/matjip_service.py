"""맛집 포스팅 소재 수집 — 플레이스 방문자 리뷰 + 블로그 후기를 모아 원고 소재(source_data)로 만든다.

네이버 스크래핑이라 클라우드(데이터센터 IP)에선 막히므로 로컬 에이전트(집 IP)에서 실행된다.
설치형(local)은 백엔드가 직접 호출한다.
"""


async def collect_matjip_source(place_url: str = "", keyword: str = "", log=None) -> dict:
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

    # 1) 플레이스 방문자 리뷰
    if place_url:
        try:
            _log("플레이스 방문자 리뷰 수집 중...")
            from mbam_nextgen.services.place_review_service import PlaceReviewService
            d = await PlaceReviewService().collect_reviews(place_url)
            texts = []
            for r in (d.get("reviews") or [])[:25]:
                t = r if isinstance(r, str) else (r.get("text") or r.get("content") or r.get("review") or "")
                if t and str(t).strip():
                    texts.append(f"- {str(t).strip()}")
            if texts:
                parts.append("[방문자 리뷰]\n" + "\n".join(texts))
                _log(f"방문자 리뷰 {len(texts)}건 수집")
        except Exception as e:
            _log(f"플레이스 리뷰 수집 실패(계속): {e}")

    # 2) 블로그 후기
    if keyword:
        try:
            _log(f"'{keyword}' 블로그 후기 수집 중...")
            from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
            results, _sb = await SeoAnalyzer().fetch_top_blogs(keyword, limit=5)
            n = 0
            for it in (results or [])[:5]:
                c = (it.get("content") or "")[:1200]
                if c.strip():
                    parts.append(f"[블로그 후기: {it.get('title', '')}]\n{c.strip()}")
                    n += 1
            _log(f"블로그 후기 {n}건 수집")
        except Exception as e:
            _log(f"블로그 후기 수집 실패(계속): {e}")

    source = "\n\n".join(parts).strip()
    if not source:
        raise RuntimeError("참고 소재를 수집하지 못했습니다. 플레이스 URL 또는 키워드를 확인하세요.")
    return {"success": True, "source_data": source}
