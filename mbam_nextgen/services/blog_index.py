# ==========================================
# 네이버 블로그 지수(추정) 수집·산정 서비스  (review-platform naver-blog.service.ts 의 Python 포팅)
# 공식 API에 개설일/지수 항목이 없어 모바일 공개 엔드포인트를 스크래핑한다.
# 네이버 내부 "진짜 지수"는 취득 불가(차단) → 관찰 신호로 추정 등급을 낸다(블덱스/블지수와 동일 접근).
# 가중치/밴드/등급 기준은 review-platform 기본값 그대로 유지.
#
# 봇 탐지 회피: 실제 UA 풀 회전 + 모바일 일관 헤더 + 요청 간 랜덤 지터 + 백오프 재시도(429/403/timeout)
#   - 모바일 도메인(m.blog/rss) 우선 / 페이지 수 상한으로 호출 최소화(블로그당 1일 1회 캐싱 권장)
# ⚠️ 네이버 공식 지수 아님(추정치).
# ==========================================
import asyncio
import os
import random
import re
import time
from typing import Optional

import httpx

# 실제 브라우저 UA 풀 — 요청마다 회전
_UA_POOL = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
]


def _pick_ua() -> str:
    return random.choice(_UA_POOL)


def _mobile_headers(blog_id: str, json_: bool = False) -> dict:
    h = {
        "User-Agent": _pick_ua(),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "application/json, text/plain, */*" if json_ else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": f"https://m.blog.naver.com/{blog_id}",
        "Cache-Control": "no-cache",
        "sec-ch-ua": '"Chromium";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "Upgrade-Insecure-Requests": "1",
    }
    if json_:
        h["X-Requested-With"] = "XMLHttpRequest"
    return h


async def _jitter(min_ms: int, max_ms: int):
    await asyncio.sleep((min_ms + random.random() * (max_ms - min_ms)) / 1000.0)


async def _safe_fetch(client: httpx.AsyncClient, url: str, blog_id: str, json_: bool = False,
                      retries: int = 2, timeout_ms: int = 12000) -> Optional[str]:
    """봇 회피 fetch — UA/헤더 회전 + 지터 + 백오프 재시도. 실패 시 None."""
    for attempt in range(retries + 1):
        try:
            res = await client.get(url, headers=_mobile_headers(blog_id, json_), timeout=timeout_ms / 1000.0)
            if res.status_code in (429, 403):
                await _jitter(1500 * (attempt + 1), 3000 * (attempt + 1))
                continue
            if res.status_code >= 400:
                await _jitter(500, 1200)
                continue
            return res.text
        except Exception:
            await _jitter(800 * (attempt + 1), 1600 * (attempt + 1))
    return None


def parse_blog_id(input_str: str) -> Optional[str]:
    """블로그 URL/입력에서 blogId 추출."""
    if not input_str:
        return None
    s = input_str.strip()
    q = re.search(r"[?&]blogId=([a-zA-Z0-9_-]+)", s)
    if q:
        return q.group(1)
    m = re.search(r"blog\.naver\.com/([a-zA-Z0-9_-]+)", s)
    if m and m.group(1) not in ("PostView", "PostList"):
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]+", s):
        return s
    return None


# ── 수집 ─────────────────────────────────────────────────────────────
async def _fetch_search_exposure(client: httpx.AsyncClient, blog_id: str, titles: list) -> Optional[float]:
    """네이버 공식 블로그 검색 API로 '검색 노출' 측정. 검색 API 키 없으면 None(점수 불변)."""
    cid = os.environ.get("NAVER_CLIENT_ID")
    csec = os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not csec:
        return None
    sample = [re.sub(r"<[^>]+>", "", t).strip() for t in titles]
    sample = [t for t in sample if len(t) >= 4][:3]
    if not sample:
        return None

    # 공식 API(키 인증)라 봇 회피 지터 불필요 → 3건 동시 조회로 단축
    async def _check(q: str):
        try:
            res = await client.get(
                "https://openapi.naver.com/v1/search/blog.json",
                params={"query": q, "display": 30},
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
                timeout=10,
            )
            if res.status_code >= 400:
                return None
            items = res.json().get("items", []) or []
            return any(
                blog_id in str(it.get("bloggerlink", ""))
                or f"blog.naver.com/{blog_id}" in str(it.get("link", ""))
                or f"/{blog_id}/" in str(it.get("link", ""))
                for it in items
            )
        except Exception:
            return None

    results = await asyncio.gather(*[_check(q) for q in sample])
    if any(r is None for r in results):
        return None
    return sum(1 for r in results if r) / len(results)


async def _fetch_rss_meta(client: httpx.AsyncClient, blog_id: str) -> dict:
    xml = await _safe_fetch(client, f"https://rss.blog.naver.com/{blog_id}.xml", blog_id, retries=1)
    if not xml:
        return {"title": None, "description": None, "post_dates": []}
    tm = re.search(r"<title><!\[CDATA\[([\s\S]*?)\]\]></title>", xml)
    dm = re.search(r"<description><!\[CDATA\[([\s\S]*?)\]\]></description>", xml)
    post_dates = []
    for block in xml.split("<item>")[1:]:
        m = re.search(r"<pubDate>([^<]+)</pubDate>", block)
        if m:
            ts = _parse_rfc822_ms(m.group(1).strip())
            if ts is not None:
                post_dates.append(ts)
    return {"title": tm.group(1).strip() if tm else None,
            "description": dm.group(1).strip() if dm else None,
            "post_dates": post_dates}


def _parse_rfc822_ms(s: str) -> Optional[int]:
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


async def _fetch_posts(client: httpx.AsyncClient, blog_id: str, max_pages: int = 6) -> dict:
    """모바일 글목록 JSON API를 페이지네이션해 글 메타 수집.
    1페이지가 가득 차면(30개) 나머지 페이지는 랜덤 지연(0~0.5초)만 두고 동시 요청 —
    순차+지터 방식 대비 4~5초 단축(브라우저도 리소스를 병렬 로드하므로 탐지 위험 낮음)."""
    import json as _json

    async def _page(page: int, delay: float = 0.0) -> list:
        if delay:
            await asyncio.sleep(delay)
        url = f"https://m.blog.naver.com/api/blogs/{blog_id}/post-list?categoryNo=0&itemCount=30&page={page}"
        body = await _safe_fetch(client, url, blog_id, json_=True)
        if not body:
            return []
        try:
            data = _json.loads(body)
        except Exception:
            return []
        return (data.get("result") or {}).get("items") or []

    all_items = await _page(1)
    if len(all_items) == 30 and max_pages > 1:
        rest = await asyncio.gather(*[
            _page(p, delay=random.random() * 0.5) for p in range(2, max_pages + 1)
        ])
        for items in rest:
            all_items.extend(items)

    posts = []
    blog_no = None
    for it in all_items:
        if blog_no is None and isinstance(it.get("blogNo"), int):
            blog_no = it["blogNo"]
        ms = it.get("addDate")
        try:
            ms = int(ms)
        except (TypeError, ValueError):
            continue
        if not ms:
            continue
        posts.append({
            "date": ms,
            "comments": int(it.get("commentCnt") or 0),
            "sympathy": int(it.get("sympathyCnt") or 0),
            "category": str(it.get("categoryName") or "").strip(),
            "title": str(it.get("titleWithInspectMessage") or it.get("title") or "").strip(),
        })
    return {"posts": posts, "blog_no": blog_no}


async def _fetch_blog_home(client: httpx.AsyncClient, blog_id: str) -> dict:
    empty = {"total_post_count": None, "subscriber_count": None, "total_visitor_count": None, "day_visitor_count": None}
    html = await _safe_fetch(client, f"https://m.blog.naver.com/{blog_id}", blog_id, retries=1)
    if not html:
        return empty

    def num(pattern):
        m = re.search(pattern, html)
        return int(m.group(1)) if m else None

    return {
        "total_post_count": num(r'"postCount":(\d+)'),
        "subscriber_count": num(r'"subscriberCount":(\d+)'),
        "total_visitor_count": num(r'"totalVisitorCount":(\d+)'),
        "day_visitor_count": num(r'"dayVisitorCount":(\d+)'),
    }


async def _fetch_oldest_post_date(client: httpx.AsyncClient, blog_id: str, total_post_count: Optional[int]) -> Optional[int]:
    """진짜 개설일(첫 글) — 총 글수로 마지막 페이지를 계산해 가장 오래된 글 날짜."""
    if not total_post_count or total_post_count <= 30:
        return None
    page = -(-total_post_count // 30)  # ceil
    tries = 0
    import json as _json
    while tries < 3 and page >= 1:
        body = await _safe_fetch(client, f"https://m.blog.naver.com/api/blogs/{blog_id}/post-list?categoryNo=0&itemCount=30&page={page}", blog_id, json_=True)
        if body:
            try:
                data = _json.loads(body)
                items = (data.get("result") or {}).get("items") or []
                dates = [int(it["addDate"]) for it in items if it.get("addDate")]
                if dates:
                    return min(dates)
            except Exception:
                pass
        tries += 1
        page -= 1
    return None


async def fetch_blog_stats(blog_url_or_id: str) -> Optional[dict]:
    """블로그 통계 수집. 실패 시 None."""
    blog_id = parse_blog_id(blog_url_or_id)
    if not blog_id:
        return None

    async with httpx.AsyncClient(follow_redirects=True) as client:
        posts_res, rss, home = await asyncio.gather(
            _fetch_posts(client, blog_id),
            _fetch_rss_meta(client, blog_id),
            _fetch_blog_home(client, blog_id),
        )
        posts = posts_res["posts"]
        blog_no = posts_res["blog_no"]

        if not posts and not rss["post_dates"]:
            return None

        now = int(time.time() * 1000)
        DAY = 86400000

        # 글목록 API + RSS 발행일 합쳐 '일' 단위 dedup
        day_keys = set()
        merged = []
        for ms in [p["date"] for p in posts] + rss["post_dates"]:
            key = time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
            if key not in day_keys:
                day_keys.add(key)
                merged.append(ms)
        merged.sort()
        first_post_date = merged[0]
        last_post_date = merged[-1]

        # 개설일(마지막 페이지)과 검색노출은 서로 독립 → 동시 실행으로 단축
        recent_titles_early = [p["title"] for p in sorted(posts, key=lambda x: x["date"], reverse=True) if p["title"]]
        if home["total_post_count"] and home["total_post_count"] > len(posts):
            oldest, search_exposure = await asyncio.gather(
                _fetch_oldest_post_date(client, blog_id, home["total_post_count"]),
                _fetch_search_exposure(client, blog_id, recent_titles_early),
            )
            if oldest and oldest < first_post_date:
                first_post_date = oldest
        else:
            search_exposure = await _fetch_search_exposure(client, blog_id, recent_titles_early)

        recent_30 = len([ms for ms in merged if now - ms <= 30 * DAY])
        recent_90 = len([ms for ms in merged if now - ms <= 90 * DAY])

        total_comments = sum(p["comments"] for p in posts)
        total_sympathy = sum(p["sympathy"] for p in posts)

        cat_count = {}
        for p in posts:
            if p["category"]:
                cat_count[p["category"]] = cat_count.get(p["category"], 0) + 1
        top_category, top_count = None, 0
        for cat, cnt in cat_count.items():
            if cnt > top_count:
                top_count, top_category = cnt, cat
        category_concentration = (top_count / len(posts)) if posts else 0.0

        return {
            "blog_id": blog_id,
            "blog_no": blog_no,
            "title": rss["title"],
            "description": rss["description"],
            "first_post_date": first_post_date,
            "last_post_date": last_post_date,
            "post_count": len(posts),
            "recent_post_count_30d": recent_30,
            "recent_post_count_90d": recent_90,
            "avg_comments": (total_comments / len(posts)) if posts else 0,
            "avg_sympathy": (total_sympathy / len(posts)) if posts else 0,
            "top_category": top_category,
            "category_concentration": category_concentration,
            "search_exposure": search_exposure,
            "total_post_count": home["total_post_count"],
            "subscriber_count": home["subscriber_count"],
            "total_visitor_count": home["total_visitor_count"],
            "day_visitor_count": home["day_visitor_count"],
            "collected_at": now,
        }


# ── 산정 (review-platform 기본값 그대로) ──────────────────────────────
# "잠재 품질" 가중치(합 100) — 누적 신호. 활동은 operationFactor(곱셈 게이트)로 처리.
BLOG_INDEX_WEIGHTS_V2 = {
    "audience": 24, "traffic": 22, "engagement": 18, "volume": 16, "age": 14, "consistency": 6,
}

# 구간(밴드) 점수표 — [상한(미만), 점수]
_AGE_BANDS = [(6, 20), (12, 30), (24, 40), (36, 50), (60, 60), (120, 70), (180, 80), (240, 90), (float("inf"), 100)]
_VOLUME_BANDS = [(50, 15), (150, 35), (300, 55), (600, 70), (1000, 85), (float("inf"), 100)]
_AUDIENCE_BANDS = [(100, 10), (300, 25), (700, 45), (1500, 65), (3000, 80), (6000, 90), (float("inf"), 100)]
_TRAFFIC_CUM_BANDS = [(100, 10), (500, 20), (1000, 30), (5000, 40), (10000, 50), (100000, 60), (300000, 70), (600000, 80), (1000000, 90), (float("inf"), 100)]
_TRAFFIC_DAILY_BANDS = [(10, 10), (50, 25), (200, 40), (500, 55), (1000, 65), (3000, 80), (10000, 90), (float("inf"), 100)]
_TRAFFIC_CUM_RATIO = 0.6
_TRAFFIC_DAILY_RATIO = 0.4

# 객관 지수 Level 1~15 — Level i 의 최소 점수
_BLOG_LEVEL_MIN_SCORES = [0, 8, 15, 22, 30, 38, 46, 54, 62, 70, 77, 84, 90, 95, 98]

# 0~100 → 8단계 라벨 (내림차순)
_BLOG_TIER_BANDS = [
    (94, "최적5"), (88, "최적4"), (82, "최적3"), (76, "최적2"), (70, "최적1"),
    (67, "준최적8"), (65, "준최적7"), (62, "준최적6"), (60, "준최적5"),
    (57, "준최적4"), (55, "준최적3"), (52, "준최적2"), (50, "준최적1"),
    (30, "일반"), (0, "저품질"),
]


def _band_score(value, bands):
    for ceil, score in bands:
        if value < ceil:
            return score
    return bands[-1][1]


def _clamp01(x):
    return max(0.0, min(1.0, x))


def score_to_tier(score):
    for mn, label in _BLOG_TIER_BANDS:
        if score >= mn:
            return label
    return "저품질"


def score_to_level(score):
    level = 1
    for i in range(14, -1, -1):
        if score >= _BLOG_LEVEL_MIN_SCORES[i]:
            level = i + 1
            break
    return {"level": level, "level_label": score_to_tier(score)}


def score_to_grade(score):
    tier = score_to_tier(score)
    grade = 1 if score >= 76 else 2 if score >= 67 else 3 if score >= 62 else 4 if score >= 55 else 5
    return {"grade": grade, "tier": tier}


def estimate_blog_index(stats: dict) -> dict:
    now = int(time.time() * 1000)
    DAY = 86400000
    W = BLOG_INDEX_WEIGHTS_V2

    # 1) 잠재 품질(누적 신호)
    months = ((now - stats["first_post_date"]) / (30 * DAY)) if stats.get("first_post_date") else 0
    age_n = _band_score(months, _AGE_BANDS) / 100
    post_count_for_volume = stats.get("total_post_count") or stats["post_count"]
    volume_n = _band_score(post_count_for_volume, _VOLUME_BANDS) / 100
    engagement_n = _clamp01((stats["avg_comments"] + stats["avg_sympathy"]) / 15)
    consistency_n = stats["category_concentration"] if stats["post_count"] >= 5 else stats["category_concentration"] * 0.5
    audience_n = _band_score(stats.get("subscriber_count") or 0, _AUDIENCE_BANDS) / 100

    total_visitors = stats.get("total_visitor_count") or 0
    operating_days = max(1, (now - stats["first_post_date"]) / DAY) if stats.get("first_post_date") else 1
    daily_avg_visitors = total_visitors / operating_days
    traffic_n = (_band_score(total_visitors, _TRAFFIC_CUM_BANDS) * _TRAFFIC_CUM_RATIO
                 + _band_score(daily_avg_visitors, _TRAFFIC_DAILY_BANDS) * _TRAFFIC_DAILY_RATIO) / 100

    breakdown = {
        "audience": round(audience_n * W["audience"]),
        "traffic": round(traffic_n * W["traffic"]),
        "engagement": round(engagement_n * W["engagement"]),
        "volume": round(volume_n * W["volume"]),
        "age": round(age_n * W["age"]),
        "consistency": round(consistency_n * W["consistency"]),
    }
    quality_base = min(100, sum(breakdown.values()))

    if stats.get("search_exposure") is not None:
        exposure_raw = round(stats["search_exposure"] * 100)
        quality_base = round(quality_base * 0.7 + exposure_raw * 0.3)
        breakdown["exposureRaw"] = exposure_raw

    # 2) 운영 활성도(곱셈 게이트)
    last_ms = stats.get("last_post_date") or stats.get("first_post_date") or now
    months_since_last = (now - last_ms) / (30 * DAY)
    freq90 = _clamp01(stats["recent_post_count_90d"] / 9)
    if months_since_last <= 1:
        recency = 1.0
    elif months_since_last <= 2:
        recency = 0.8
    elif months_since_last <= 3:
        recency = 0.6
    elif months_since_last <= 6:
        recency = 0.4
    elif months_since_last <= 12:
        recency = 0.25
    else:
        recency = 0.15
    operation_factor = max(0.15, min(1.0, recency * 0.4 + freq90 * 0.6))

    # 3) 최종 지수 = 잠재품질 × 운영활성도
    score = round(quality_base * operation_factor)

    # 나이 기반 "최소 등급 바닥"
    if months >= 24:
        score = max(score, 50 if stats["recent_post_count_90d"] >= 1 else 30)
    elif months < 6:
        score = max(score, 30)

    g = score_to_grade(score)
    lv = score_to_level(score)
    return {
        "score": score,
        "grade": g["grade"],
        "tier": g["tier"],
        "level": lv["level"],
        "level_label": lv["level_label"],
        "operation_factor": round(operation_factor, 3),
        "quality_base": quality_base,
        "breakdown": breakdown,
    }


async def analyze_blog(blog_url_or_id: str) -> Optional[dict]:
    """URL 1콜로 통계 수집 + 지수 산정. 실패 시 None."""
    stats = await fetch_blog_stats(blog_url_or_id)
    if not stats:
        return None
    return {"stats": stats, "index": estimate_blog_index(stats)}
