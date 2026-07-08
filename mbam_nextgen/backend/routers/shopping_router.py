from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel
import asyncio
import httpx
import re
from typing import List, Optional, Dict
import math
import urllib.parse

import os as _os
if (_os.environ.get("EXECUTION_MODE", "local") or "").strip().lower() == "cloud":
    kiwi = None  # [슬림] 클라우드는 분석을 에이전트에 위임 → Kiwi 형태소 모델 미로드(OOM 방지)
else:
    try:
        from kiwipiepy import Kiwi
        kiwi = Kiwi()
    except ImportError:
        kiwi = None

from mbam_nextgen.backend.quota import check_quota, increment_quota

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

# ==========================================
# 1. 유틸리티 (형태소 분석 및 정제)
# ==========================================

SPAM_WORDS = {'특가', '무료배송', '이벤트', '신상', '쿠폰', '할인', '정품', '사은품', '당일발송'}

# 상품명에 부적합한 '정보/질문형' 연관어(검색 의도가 구매가 아닌 '정보탐색') → 상품명 토큰 풀에서 제외.
# 예: 그릭요거트 가격/성분/유통기한/효능/먹는법 … 은 정보성이라 상품명에 넣으면 어색.
INFO_STOPWORDS = {
    '가격', '최저가', '가격비교', '성분', '원재료', '재료', '유통기한', '기한', '보관', '보관법', '보관방법',
    '위치', '파는곳', '판매처', '매장', '어디', '냄새', '유당', '함량', '칼로리', '효능', '효과', '부작용',
    '후기', '리뷰', '디시', '정보', '방법', '만들기', '만드는법', '먹는법', '먹는방법', '레시피', '요리',
    '차이', '비교', '사용법', '뜻', '직구', '냉동', '해동', '추천', '순위', '내돈내산', '협찬',
    '유통', '요즘', '영어', '일본어', '중국어', '한글', '발음', '실비', '정가', '가품', '가짜', '진품', '종류',
}

# 태그 풀에서 추가로 거르는 단위·조각성·판매채널 단어(상품명/태그에 부적합).
TAG_STOPWORDS = {
    # 단위(숫자 떨어진 조각)
    'kg', 'g', 'ml', 'l', 'cc', 'mg', '리터', '그램', '키로', '킬로',
    # 판매/배송 채널성
    '정기', '정기배송', '배달', '납품', '판매', '구매', '주문', '도매', '소매', '직배',
    '당일', '새벽', '새벽배송', '당일배송', '택배', '무배',
    # 조각/오타성
    '무당', '대용', '시설', '밀폐', '용기', '해썹', '인증', '국내', '국산지',
}

_UNIT_RE = re.compile(r'^\d*(kg|g|ml|l|cc|mg|t|매|개|입|팩)$', re.IGNORECASE)

# Utility functions imported from keyword_seo
from mbam_nextgen.services.keyword_seo import analyze_seo_keyword, clean_and_tokenize, fetch_autocomplete_related, fetch_search_ad_keywords, fetch_top_10_shopping

# 상품 '형태/타입' 속성어(상품명에 적합) — 분류용
ATTR_TYPE_WORDS = {
    '무가당', '가당', '플레인', '냉장', '상온', '분말', '파우더', '액상', '스틱', '오리지널',
    '저지방', '무지방', '수제', '국산', '유기농', '프리미엄', '휴대용', '충전식', '무선', '유선',
    '미니', '초소형', '소형', '대형', '접이식', '대용량', '소용량', '저당', '제로', '고단백', '단백질',
}


def classify_tokens(tokens):
    """수집 토큰을 상품명 관점으로 분류: 용량/중량·수량/세트·형태/타입·핵심."""
    groups = {"용량중량": [], "수량세트": [], "형태타입": [], "핵심키워드": []}
    for t in tokens:
        if re.search(r"\d", t) and re.search(r"(kg|g|ml|l|리터|리뷰)$", t.lower()):
            groups["용량중량"].append(t)
        elif t in {"대용량", "소용량", "중량"}:
            groups["용량중량"].append(t)
        elif re.search(r"\d+(개|입|팩|박스|세트|구|매)$", t) or t in {"세트", "묶음", "대량", "벌크"}:
            groups["수량세트"].append(t)
        elif t in ATTR_TYPE_WORDS:
            groups["형태타입"].append(t)
        else:
            groups["핵심키워드"].append(t)
    return groups


def _parse_vol(v):
    if isinstance(v, str):
        if "<" in v:
            return 10
        try:
            return int(float(v.replace(",", "").strip()))
        except (ValueError, TypeError):
            return 0
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def remove_duplicates_keep_order(items):
    """순서를 유지하며 중복 제거."""
    return list(dict.fromkeys(items))

# ==========================================
# 2. 키워드 분석 (모듈 1, 2)
# ==========================================

class KeywordAnalyzeRequest(BaseModel):
    seed_keyword: str

@router.post("/keyword/analyze")
async def analyze_keyword(req: KeywordAnalyzeRequest):
    """
    실제 연관 키워드(태그) 수집 + NLP 토큰 풀 추출.
    네이버 자동완성(무료)으로 시드와 '실제로 연관된' 검색어를 수집한 뒤,
    형태소 분석(Kiwi)·스팸 제거·중복 제거로 클린 토큰 풀을 만든다.
    """
    seed = req.seed_keyword.strip()
    seed_tokens = clean_and_tokenize(seed)

    # 1) 연관검색어 수집
    #    (A) 네이버 검색광고 키워드도구 = 정석(실제 연관키워드 + 검색량). 키 필요.
    #    (B) 자동완성 = 무료 보강/폴백.
    vol_map = {}
    ad_related = []
    source = "자동완성"
    seed_volume = None  # 시드 키워드 자체의 월간 검색량 (PC/모바일/합계/경쟁도)
    try:
        ad_items = await fetch_search_ad_keywords(seed)
        _seed_ns_vol = seed.replace(" ", "")
        for k in (ad_items or []):
            kw = (k.get("relKeyword") or "").strip()
            if not kw:
                continue
            pc, mo = _parse_vol(k.get("monthlyPcQcCnt", 0)), _parse_vol(k.get("monthlyMobileQcCnt", 0))
            if seed_volume is None and kw.replace(" ", "") == _seed_ns_vol:
                seed_volume = {"pc": pc, "mobile": mo, "total": pc + mo, "comp": k.get("compIdx") or "-"}
            ad_related.append(kw)
            vol_map[kw] = pc + mo
        if ad_related:
            source = "검색광고 키워드도구"
    except Exception as e:
        print("keywordstool error:", e)

    auto_related = await fetch_autocomplete_related(seed)
    if len(seed_tokens) >= 2:
        core = seed_tokens[-1]
        if core and core != seed:
            auto_related += await fetch_autocomplete_related(core)

    # 검색광고 연관어 우선(검색량순) + 자동완성 보강
    ad_related.sort(key=lambda kw: vol_map.get(kw, 0), reverse=True)
    related_raw = remove_duplicates_keep_order([r for r in (ad_related + auto_related) if r and r != seed])

    # ⭐ 관련성 필터: 시드 핵심어를 포함한 검색어만 남김(예: '그릭요거트' → '광주맛집' 제외).
    #    검색광고/자동완성은 시드와 무관한 키워드도 반환하므로, 시드 토큰/무공백 시드를 포함하는 것만 통과.
    _seed_ns = seed.replace(" ", "")
    _seed_cores = [c for c in (list(set(seed_tokens)) + [_seed_ns]) if len(c) >= 2]

    def _related_relevant(kw):
        kw_ns = kw.replace(" ", "")
        return any(c in kw_ns for c in _seed_cores)

    related = [r for r in related_raw if _related_relevant(r)]

    # (C) 쇼핑 1~N위 상품명 = 상품명용 키워드의 최고 소스(실제 판매 상품 제목). 키 필요.
    shop_titles = []
    try:
        shop_titles = await fetch_top_10_shopping(seed)
    except Exception as e:
        print("shop top error:", e)
    if shop_titles:
        source = "쇼핑Top + " + source

    seed_set = set(seed_tokens)
    seed_nospace = seed.replace(" ", "")
    # 시드 핵심어(부분 일치 필터용): 시드 토큰 + 무공백 시드
    seed_cores = {s for s in (list(seed_set) + [seed_nospace]) if len(s) >= 2}

    def _contains_seed_core(t):
        """'무가당그릭요거트'처럼 시드 핵심어를 포함한 변형 검색어 → 태그 아님(연관키워드)."""
        return any(c in t and t != c for c in seed_cores)

    def _is_tag(t):
        return (
            t not in seed_set
            and t not in INFO_STOPWORDS
            and t.lower() not in TAG_STOPWORDS    # 단위·채널·조각성 단어 제외
            and not _UNIT_RE.match(t)             # kg/ml/500g 등 단위 토큰 제외
            and t not in seed_nospace
            and not re.fullmatch(r"\d+", t)
            and 2 <= len(t) <= 6           # 너무 긴 토큰은 합성 검색어 → 태그에서 제외
            and not _contains_seed_core(t)
        )

    # 2) [태그 풀] = '네이버에 등록된 키워드'(검색광고 키워드도구/자동완성 연관어)에서만 추출.
    #    쇼핑 상품명 토큰화는 '해썹/시설/밀폐/용기' 같은 제목 조각·인증·스펙 부스러기가 섞이므로 태그 풀에서 제외.
    #    related 는 이미 ① 관련성 필터(시드 포함) ② 검색량순 정렬 적용됨 → 토큰도 그 순서/품질 유지.
    related_tokens = []
    for kw in related:
        related_tokens.extend(clean_and_tokenize(kw))

    valid_tokens_pool = remove_duplicates_keep_order([t for t in related_tokens if _is_tag(t)])
    # 연관어가 비었을 때(키 미설정 등)만 쇼핑 상품명 토큰으로 폴백
    if not valid_tokens_pool:
        shop_tokens = []
        for title in shop_titles:
            shop_tokens.extend(clean_and_tokenize(title))
        valid_tokens_pool = remove_duplicates_keep_order([t for t in shop_tokens if _is_tag(t)])

    # 3) 분류 (용량/중량·수량/세트·형태/타입·핵심)
    classified = classify_tokens(valid_tokens_pool)

    # [연관키워드] = 수집된 검색어 원문 + 검색량(검색광고 키 있을 때). 검색량순 정렬, 화면에서 분리 표시.
    related_with_volume = sorted(
        [{"keyword": kw, "volume": vol_map.get(kw, 0)} for kw in related],
        key=lambda x: x["volume"], reverse=True
    )

    return {
        "seed_keyword": seed,
        "seed_tokens": seed_tokens,
        "seed_volume": seed_volume,                  # 시드 월간 검색량 {pc, mobile, total, comp} (키 없으면 null)
        "autocomplete": remove_duplicates_keep_order(auto_related)[:15],  # 자동완성 검색어(원문)
        "related_keywords": related,                 # 연관 검색어 원문
        "related_with_volume": related_with_volume,  # 연관키워드 + 검색량(검색량순)
        "related_keywords_count": len(related),
        "valid_tokens_pool": valid_tokens_pool,      # 태그 풀(상품명/태그용 클린 토큰)
        "classified_tokens": classified,             # 그룹별 분류
        "shop_title_count": len(shop_titles),
        "source": source,
        "message": f"분석 완료 (소스: {source})"
    }

# ==========================================
# 2-1. 키워드 인사이트 (데이터랩 쇼핑인사이트: 성별/연령/월별 추이)
# ==========================================

# 네이버 쇼핑인사이트 1분류 카테고리 CID (쇼핑 검색 결과의 category1 이름 → cid)
_DATALAB_CATS = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
    "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
    "여가/생활편의": "50000009", "면세점": "50000010",
}


async def _detect_datalab_category(client, seed: str, headers: dict):
    """쇼핑 검색 상위 40개의 최빈 1분류 카테고리 → (이름, cid). 감지 실패 시 (None, None)."""
    from collections import Counter
    try:
        r = await client.get(
            f"https://openapi.naver.com/v1/search/shop.json?query={urllib.parse.quote(seed)}&display=40",
            headers=headers, timeout=8.0)
        if r.status_code != 200:
            return None, None
        names = [it.get("category1") for it in r.json().get("items", []) if it.get("category1")]
        for name, _cnt in Counter(names).most_common():
            if name in _DATALAB_CATS:
                return name, _DATALAB_CATS[name]
    except Exception as e:
        print("datalab category detect error:", e)
    return None, None


class KeywordInsightRequest(BaseModel):
    seed_keyword: str


@router.post("/keyword/insight")
async def keyword_insight(req: KeywordInsightRequest):
    """키워드 인사이트 — 성별/연령별 검색 비율 + 최근 1년 월별 추이(PC/모바일).
    네이버 데이터랩 쇼핑인사이트 API 사용(오픈API 키 필요, 애플리케이션에 '데이터랩' API 추가 필요).
    ratio 는 요청 내 최대값=100 기준의 상대지수 — 같은 요청 안의 그룹끼리 비교 가능."""
    import json
    from datetime import date, timedelta

    seed = req.seed_keyword.strip()
    if not seed:
        raise HTTPException(status_code=400, detail="키워드를 입력하세요.")
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"success": False, "error": "네이버 오픈API 키가 설정되지 않았습니다."}

    search_headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    datalab_headers = {**search_headers, "Content-Type": "application/json"}

    # 진행 중인 이번 달은 데이터가 불완전해 추이가 급락처럼 보임 → 지난달 말일까지 12개월
    end = date.today().replace(day=1) - timedelta(days=1)
    sy, sm = end.year, end.month - 11
    if sm <= 0:
        sy, sm = sy - 1, sm + 12
    start = date(sy, sm, 1)
    base_body = {
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "timeUnit": "month", "keyword": seed,
        "device": "", "gender": "", "ages": [],
    }

    async with httpx.AsyncClient() as client:
        cat_name, cid = await _detect_datalab_category(client, seed, search_headers)
        if not cid:
            return {"success": False, "error": "쇼핑 카테고리를 감지하지 못했습니다. (검색 결과 없음)"}
        body = {**base_body, "category": cid}

        async def _datalab(kind: str):
            url = f"https://openapi.naver.com/v1/datalab/shopping/category/keyword/{kind}"
            try:
                r = await client.post(url, headers=datalab_headers,
                                      content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                      timeout=10.0)
                if r.status_code != 200:
                    print(f"datalab {kind} {r.status_code}: {r.text[:200]}")
                    return None
                results = r.json().get("results") or []
                return (results[0].get("data") or []) if results else []
            except Exception as e:
                print(f"datalab {kind} error:", e)
                return None

        g_data, a_data, d_data = await asyncio.gather(_datalab("gender"), _datalab("age"), _datalab("device"))

    if g_data is None and a_data is None and d_data is None:
        return {"success": False,
                "error": "데이터랩 조회 실패 — developers.naver.com 애플리케이션에 '데이터랩(쇼핑인사이트)' API가 추가되어 있는지 확인하세요."}

    # 성별: 기간 전체 ratio 합산 → 비율(%)
    gender = None
    if g_data:
        sums = {"f": 0.0, "m": 0.0}
        for d in g_data:
            if d.get("group") in sums:
                sums[d["group"]] += float(d.get("ratio") or 0)
        tot = sums["f"] + sums["m"]
        if tot > 0:
            gender = {"female": round(sums["f"] / tot * 100, 1), "male": round(sums["m"] / tot * 100, 1)}

    # 연령: 10~60 그룹 합산, 50+60 은 '50대+' 로 합침 → 비율(%)
    ages = None
    if a_data:
        sums = {}
        for d in a_data:
            g = str(d.get("group") or "")
            sums[g] = sums.get(g, 0.0) + float(d.get("ratio") or 0)
        tot = sum(sums.values())
        if tot > 0:
            def pct(*groups):
                return round(sum(sums.get(g, 0.0) for g in groups) / tot * 100, 1)
            ages = [
                {"label": "10대", "pct": pct("10")}, {"label": "20대", "pct": pct("20")},
                {"label": "30대", "pct": pct("30")}, {"label": "40대", "pct": pct("40")},
                {"label": "50대+", "pct": pct("50", "60")},
            ]

    # 월별 추이: 같은 요청 안의 pc/mo ratio → 정규화 공유로 비교 가능. total = pc + mo
    trend = None
    if d_data:
        months = {}
        for d in d_data:
            period = str(d.get("period") or "")[:7]   # YYYY-MM
            if not period:
                continue
            row = months.setdefault(period, {"pc": 0.0, "mobile": 0.0})
            if d.get("group") == "pc":
                row["pc"] += float(d.get("ratio") or 0)
            elif d.get("group") == "mo":
                row["mobile"] += float(d.get("ratio") or 0)
        trend = [
            {"month": k[2:].replace("-", "-"), "pc": round(v["pc"], 1),
             "mobile": round(v["mobile"], 1), "total": round(v["pc"] + v["mobile"], 1)}
            for k, v in sorted(months.items())
        ]

    return {"success": True, "keyword": seed, "category": cat_name,
            "gender": gender, "ages": ages, "trend": trend}


# ==========================================
# 3. 상품명 조립 (모듈 3, 4)
# ==========================================

class TitleAssembleRequest(BaseModel):
    brand_name: Optional[str] = ""
    seed_keyword: str
    tokens: List[str] 
    ai_modifiers: Optional[List[str]] = []

@router.post("/keyword/assemble")
async def assemble_title(req: TitleAssembleRequest):
    """
    50자 이내 SEO 최적화 상품명 조립
    """
    # 요청에서 값 추출 (이전: seed/brand/front_tokens 미정의로 NameError 발생)
    seed = (req.seed_keyword or "").strip()
    brand = (req.brand_name or "").strip()
    # 최신성 버프: 토큰 풀의 앞쪽 일부를 시드/브랜드보다 먼저(전진) 배치
    front_tokens = list(req.tokens[:2]) if req.tokens else []

    title = ""
    # 중복 방지를 위해 시드와 브랜드명을 단어 단위로 쪼개어 used_words에 넣음
    used_words = set()
    if seed: used_words.update(seed.split())
    if brand: used_words.update(brand.split())

    for t in front_tokens:
        if t not in used_words:
            title += f"{t} "
            used_words.add(t)
            
    # 브랜드명과 시드키워드 중복 방지 스마트 결합
    if brand and seed:
        # 완전히 동일하거나 포함관계일 경우 긴 쪽만 사용
        if brand in seed:
            title += f"{seed} "
        elif seed in brand:
            title += f"{brand} "
        else:
            title += f"{brand} {seed} "
    elif brand:
        title += f"{brand} "
    elif seed:
        title += f"{seed} "
    
    for token in req.tokens:
        if token not in used_words:
            if len(title) + len(token) + 1 <= 50:
                title += f"{token} "
                used_words.add(token)
            else:
                break
                
    title = title.strip()
    
    # 추천 태그는 ai_modifiers(AI가 분석한 수식어나 연관검색어) 중 사용되지 않은 것을 우선 추천
    pool = req.ai_modifiers if req.ai_modifiers else req.tokens
    # 중복 제거 및 순서 유지
    seen = set(used_words)
    recommended = []
    for t in pool:
        if t not in seen:
            recommended.append(t)
            seen.add(t)
            
    return {
        "optimized_title": title,
        "length": len(title),
        "recommended_tags": recommended[:15],
        "warning": "상품명에 특수문자나 쉼표가 포함되면 네이버 SEO 어뷰징 패널티를 받을 수 있습니다." if any(c in title for c in ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")", ",", ".", "[", "]"]) else None
    }


class TitleSuggestRequest(BaseModel):
    brand_name: Optional[str] = ""
    seed_keyword: str

@router.post("/keyword/analyze-and-suggest")
async def analyze_and_suggest_title(req: TitleSuggestRequest):
    """
    네이버 1~40위 경쟁사 상품명을 실시간으로 수집/분석하여
    최신성 버프(롱테일 키워드 전진 배치)를 활용한 최적의 상품명 3가지를 제안합니다.
    """
    import os
    import httpx
    import re
    from collections import Counter
    from dotenv import dotenv_values

    # Load env dynamically to get the latest keys without server restart
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    env = dotenv_values(env_path)

    def _key(k):
        # 클라우드는 재배포 시 .env 파일이 초기화됨 → os.environ(DB 주입 포함) 폴백 필수
        return env.get(k) or os.environ.get(k, "")

    seed = req.seed_keyword.strip()
    brand = req.brand_name.strip() if req.brand_name else ""

    client_id = _key("NAVER_CLIENT_ID")
    client_secret = _key("NAVER_CLIENT_SECRET")
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    
    # 1. 네이버 쇼핑 검색결과 (1~40위 상품명 수집)
    titles = []
    if client_id and client_secret:
        async with httpx.AsyncClient() as client:
            url = f"https://openapi.naver.com/v1/search/shop.json?query={urllib.parse.quote(seed)}&display=40"
            try:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    items = res.json().get("items", [])
                    for item in items:
                        title = item.get("title", "").replace("<b>","").replace("</b>","")
                        titles.append(title)
            except Exception:
                pass

    # 2. 연관 키워드 및 검색량 수집 (네이버 검색광고 API)
    related_keywords = []
    volume_dict = {} # keyword -> volume mapping
    ad_customer_id = _key("NAVER_CUSTOMER_ID")
    ad_access_license = _key("NAVER_ACCESS_LICENSE")
    ad_secret_key = _key("NAVER_SECRET_KEY")
    
    if ad_customer_id and ad_access_license and ad_secret_key:
        import time, urllib.parse, hmac, hashlib, base64
        method = "GET"
        uri = "/keywordstool"
        timestamp = str(int(round(time.time() * 1000)))
        message = timestamp + "." + method + "." + uri
        
        hash_obj = hmac.new(bytes(ad_secret_key, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        
        ad_headers = {
            "X-Timestamp": timestamp,
            "X-API-KEY": ad_access_license,
            "X-Customer": str(ad_customer_id),
            "X-Signature": signature
        }
        
        async with httpx.AsyncClient() as client:
            # Naver Ad API rejects spaces. Split by space to get individual words, then comma-separate them (max 5 hints)
            words = list(dict.fromkeys(f"{brand} {seed}".split()))[:5]
            query_keyword = ",".join(words)
            ad_url = f"https://api.naver.com{uri}?hintKeywords={urllib.parse.quote(query_keyword)}&showDetail=1"
            try:
                ad_res = await client.get(ad_url, headers=ad_headers, follow_redirects=True, timeout=5.0)
                if ad_res.status_code == 200:
                    kwds = ad_res.json().get("keywordList", [])[:100]
                    for k in kwds:
                        vol = k.get('monthlyPcQcCnt', 0)
                        if isinstance(vol, str): vol = 10 if vol == '< 10' else int(vol)
                        mvol = k.get('monthlyMobileQcCnt', 0)
                        if isinstance(mvol, str): mvol = 10 if mvol == '< 10' else int(mvol)
                        total_vol = vol + mvol
                        rel_kw = k['relKeyword']
                        related_keywords.append({
                            "keyword": rel_kw,
                            "volume": total_vol,
                            "pc_vol": vol,
                            "mo_vol": mvol
                        })
                        volume_dict[rel_kw] = total_vol
            except Exception as e:
                print("Ad API Error:", e)

    # 3. Top 40 상품명 형태소 분해 및 빈도 측정
    words = []
    for title in titles:
        # 단어 분리 (간단히 띄어쓰기 및 특수문자 제거 후 분할)
        parts = re.findall(r'[가-힣a-zA-Z0-9]+', title)
        for p in parts:
            if len(p) > 1 and p not in seed and p not in brand:
                words.append(p)
                
    # 자주 쓰이는 수식어 (경쟁사 트렌드 키워드) 추출
    common_words_tuples = Counter(words).most_common(100)
    common_words = [w[0] for w in common_words_tuples]
    
    # ★ 핵심 로직: Top 40 수식어 중 "연관 검색어"에 존재하는 수식어만 진짜 알짜 수식어로 필터링
    valid_common_words = [w for w in common_words if any(w in kw for kw in volume_dict.keys())]
    
    # 만약 필터링 결과가 아예 없으면 (예외 상황), 원본을 그대로 사용
    if not valid_common_words:
        valid_common_words = common_words
    
    # 4. 연관검색어 검색량 기반으로 진짜 "롱테일(저볼륨)" 추출
    def get_vol(w):
        if w in volume_dict: return volume_dict[w]
        matches = [vol for kw, vol in volume_dict.items() if w in kw]
        if matches: return min(matches)
        return 999999

    # 진짜 롱테일(저볼륨) 순으로 정렬된 키워드 풀
    volume_sorted_words = sorted(valid_common_words[:30], key=get_vol)
    
    # 전략 수립에 사용할 최종 후보군
    trend_modifiers = valid_common_words[:15] # 연관성이 검증된 빈도수 높은 수식어들
    long_tail_modifiers = [w for w in volume_sorted_words if get_vol(w) < 50000] # 볼륨이 비교적 낮은 알짜 롱테일
    if not long_tail_modifiers:
        long_tail_modifiers = volume_sorted_words[:5]

    suggestions = []
    
    # [전략 1] 최신성 버프 집중형 (저볼륨 롱테일 전진 배치)
    t1 = []
    if brand: t1.append(brand)
    # 진짜 검색량 낮은 롱테일 키워드 1~2개를 가장 먼저 배치!
    if len(long_tail_modifiers) > 0: t1.append(long_tail_modifiers[0])
    if len(long_tail_modifiers) > 1: t1.append(long_tail_modifiers[1])
    t1.append(seed) # 그 다음 메인 시드
    
    for cw in trend_modifiers:
        if cw not in t1 and sum(len(c)+1 for c in t1) + len(cw) <= 49:
            t1.append(cw)
            
    suggestions.append({
        "strategy": "신규 상품 최신성(Freshness) 롱테일 전략",
        "desc": "실제 검색량이 낮은 연관 롱테일 키워드를 전진 배치하여 신규 등록 버프를 극대화합니다.",
        "title": " ".join(t1)
    })
    
    # [전략 2] SEO 정석 밸런스 전략
    t2 = []
    if brand: t2.append(brand)
    t2.append(seed)
    if len(long_tail_modifiers) > 2: t2.append(long_tail_modifiers[2])
    for cw in trend_modifiers:
        if cw not in t2 and sum(len(c)+1 for c in t2) + len(cw) <= 49:
            t2.append(cw)
            
    suggestions.append({
        "strategy": "SEO 정석 밸런스 전략",
        "desc": "브랜드와 메인 키워드를 빠르게 타겟팅한 후 보조 키워드들을 분산 배치합니다.",
        "title": " ".join(t2)
    })
    
    # [전략 3] 경쟁사 모방 랭커형
    t3 = []
    if brand: t3.append(brand)
    t3.append(seed)
    for cw in trend_modifiers: # 롱테일 상관없이 1~40위가 많이 쓴 빈도수 순으로 꽉 채움
        if cw not in t3 and sum(len(c)+1 for c in t3) + len(cw) <= 49:
            t3.append(cw)
            
    suggestions.append({
        "strategy": "상위 40위 랭커 벤치마킹 전략",
        "desc": "현재 1~40위가 가장 많이 사용하는 인기 수식어(트렌드)를 빈도수 순으로 꽉 채웁니다.",
        "title": " ".join(t3)
    })

    return {
        "seed": seed,
        "brand": brand,
        "top_modifiers": trend_modifiers,
        "suggestions": suggestions,
        "related_keywords": related_keywords
    }

# ==========================================
# 4. 쇼핑 순위 딥 서치 & 스코어 산출 (랭킹 모듈 - Ultimate Hybrid)
# ==========================================
from dotenv import load_dotenv
import os
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import concurrent.futures
import asyncio
from mbam_nextgen.backend.database import get_db, ShoppingTrackedItem, ShoppingHistory
from sqlalchemy.orm import Session

# 전역 ThreadPoolExecutor 선언 (동시 브라우저 실행 갯수 제한)
playwright_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# 네이버 쇼핑 차단 우회용 (로그인 가능 영구 프로필 + 테더링 IP 회전 + 프록시 준비)
from mbam_nextgen.infrastructure.proxy import ProxyManager
from mbam_nextgen.infrastructure.session import get_profile_dir as _get_profile_dir
_shopping_proxy_mgr = ProxyManager()
# 차단/캡차 페이지 식별 키워드
SHOPPING_BLOCK_KEYWORDS = ("일시적으로 제한", "비정상적인 접근", "보안 확인을 완료", "보안확인", "로봇이 아닙니다")

def _shopping_proxy_config():
    """웹배포 후 프록시: 환경변수 SHOPPING_PROXY가 있으면 그 프록시를 사용(예: http://user:pass@host:port).
    없으면 None(로컬은 테더링으로 IP를 바꾸므로 per-browser 프록시 불필요)."""
    try:
        return ProxyManager.get_browser_proxy_config(os.environ.get("SHOPPING_PROXY"))
    except Exception:
        return None
from fastapi import Depends, HTTPException, APIRouter, Query
from pydantic import BaseModel
import math
import re
import httpx
from datetime import datetime, timedelta
import json
from typing import Optional, List, Dict, Any

class AnalyzeRequest(BaseModel):
    keyword: str
    target_mid: str = ""
    store_name: str = ""
    product_name: str = ""
    compare_days: int = 1

def log_scale(x):
    return math.log(1 + x)

def min_max_norm(x, min_val, max_val):
    if max_val == min_val: return 0.0
    return (x - min_val) / (max_val - min_val)

async def fetch_target_rank_via_api(keyword: str, store_name: str, product_name: str, mid: str):
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret: return 0, None, []
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    
    target_item = None
    target_rank = 0
    top_api_items = []
    
    async with httpx.AsyncClient() as client:
        for start in [1, 101, 201, 301]:
            url = f"https://openapi.naver.com/v1/search/shop.json?query={urllib.parse.quote(keyword)}&display=100&start={start}"
            try:
                response = await client.get(url, headers=headers, timeout=5.0)
                if response.status_code != 200: continue
                data = response.json()
                items = data.get("items", [])
                for idx, item in enumerate(items):
                    global_rank = start + idx
                    is_match = False
                    if mid and mid == item.get("productId"): is_match = True
                    elif store_name and store_name.replace(" ","").lower() in item.get("mallName", "").replace(" ","").lower(): is_match = True
                    elif product_name and product_name.replace(" ","").lower() in item.get("title", "").replace("<b>","").replace("</b>","").replace(" ","").lower(): is_match = True
                    if is_match:
                        clean_title = item.get("title", "").replace("<b>","").replace("</b>","")
                        target_item = {
                            "title": clean_title,
                            "mallName": item.get("mallName"),
                            "productId": item.get("productId"),
                            "link": item.get("link"),
                            "category": f"{item.get('category1', '')} > {item.get('category2', '')}"
                        }
                        target_rank = global_rank
                    
                    clean_title = item.get("title", "").replace("<b>","").replace("</b>","")
                    top_api_items.append({
                        "rank": global_rank,
                        "title": clean_title,
                        "storeName": item.get("mallName", ""),
                        "price": int(item.get("lprice", 0)) if item.get("lprice") else 0,
                        "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 0,
                        "is_target": is_match,
                        "mid": item.get("productId", ""),
                        "category": f"{item.get('category1', '')}",
                        "is_new": False
                    })
                # Removed early break to ensure all 400 items are fetched
            except Exception:
                pass
    return target_rank, target_item, top_api_items

@router.post("/analyze-keyword")
async def analyze_keyword_shopping(req: AnalyzeRequest, db: Session = Depends(get_db), current_user: dict = Depends(check_quota)):
    if not (req.store_name or req.product_name or req.target_mid):
        raise HTTPException(status_code=400, detail="타겟 조건 누락")
        
    if req.store_name and req.store_name.isdigit() and len(req.store_name) >= 5:
        req.target_mid = req.store_name
        req.store_name = ""
        
    api_rank, api_data, top_api_items = await fetch_target_rank_via_api(req.keyword, req.store_name, req.product_name, req.target_mid)
    
    top_competitors = []
    target_stats = None
    
    # 차단 회피: 기기인증(로그인)된 네이버 계정 프로필이 있으면 그걸 사용(신뢰 기기 → 캡차 감소). 없으면 전용 프로필.
    _scrape_profile = "shopping_scraper"
    try:
        from mbam_nextgen.backend.database import NaverAccount as _NA
        from mbam_nextgen.infrastructure.session import is_registered as _is_reg
        _uid = current_user.get("sub")
        for _a in db.query(_NA).filter(_NA.user_id == _uid).all():
            if _is_reg(_a.naver_id):
                _scrape_profile = _a.naver_id
                break
    except Exception:
        pass

    blocked_flag = {"v": False}
    def scrape_sync():
        with sync_playwright() as p:
            # 차단 우회: 영구 프로필(쿠키 누적/로그인 가능) + 비헤드리스 + (배포 시) 프록시
            profile_dir = _get_profile_dir(_scrape_profile)
            ctx_opts = dict(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--window-size=1920,1080',
                ],
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR", timezone_id="Asia/Seoul",
            )
            pc = _shopping_proxy_config()
            if pc:
                ctx_opts["proxy"] = pc
            context = p.chromium.launch_persistent_context(profile_dir, **ctx_opts)
            page = context.pages[0] if context.pages else context.new_page()
            try:
                stealth(page)
            except Exception:
                pass

            def scrape_page(pg_num):
                url = f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(req.keyword)}&pagingIndex={pg_num}&pagingSize=40"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
                # 차단/캡차 페이지 감지 → 상위에서 테더링 IP 회전 후 재시도
                try:
                    body_txt = page.inner_text("body")[:400]
                except Exception:
                    body_txt = ""
                if any(k in body_txt for k in SHOPPING_BLOCK_KEYWORDS):
                    blocked_flag["v"] = True
                    return []
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(700)
                items = page.query_selector_all(
                    "[class^='product_item__'], [class^='basicList_item__'], "
                    "[class*='product_item'], [class*='basicList_item'], "
                    "[class*='adProduct_item'], [class*='basicProductCard'], "
                    "[class*='superSavingProduct'], div[class*='product_list_item'], li[data-shp-page-key]"
                )
                # 진단: 항목 수 + 첫 항목 class/텍스트 (차단인지 vs 파싱 실패인지 판별)
                try:
                    first_cls = items[0].get_attribute("class") if items else ""
                    first_txt = (items[0].inner_text()[:200].replace("\n", " ")) if items else body_txt[:200]
                    print(f"[shopping] pg{pg_num} items={len(items)} firstClass={first_cls!r} firstText={first_txt!r}")
                except Exception:
                    pass

                results = []
                for idx, item in enumerate(items):
                    html_content = item.inner_text()
                    html_content = html_content.replace('\\n', ' ')
                    
                    review_match = re.search(r'리뷰(?!별점)[^\d]*?([0-9,\.]+\s*만?)', html_content)
                    purchase_match = re.search(r'(?:구매|판매)[^\d]*?([0-9,\.]+\s*만?)', html_content)
                    keep_match = re.search(r'찜[^\d]*?([0-9,\.]+\s*만?)', html_content)
                    
                    def parse_num(m):
                        if not m: return 0
                        try:
                            val = m.group(1).replace(',', '').replace(' ', '')
                            if '만' in val:
                                return int(float(val.replace('만', '')) * 10000)
                            return int(float(val))
                        except Exception:
                            return 0

                    reviews = parse_num(review_match)
                    purchases = parse_num(purchase_match)
                    keeps = parse_num(keep_match)
                    
                    price_match = re.search(r'([0-9,]+)원', html_content)
                    price = int(price_match.group(1).replace(',', '')) if price_match else 0
                    
                    title_match = re.search(r'^(.*?)(?:\\s*(?:찜|리뷰|구매|무료배송))', html_content)
                    title_snippet = title_match.group(1).strip()[:30] if title_match else html_content[:30]
                    
                    tokens = clean_and_tokenize(req.keyword)
                    match_count = sum(1 for t in tokens if t in html_content)
                    n1_base = int((match_count / len(tokens)) * 100) if tokens else 0
                    
                    current_rank = ((pg_num - 1) * 40) + idx + 1
                    is_match = False
                    if req.target_mid and req.target_mid in html_content: is_match = True
                    elif req.store_name and req.store_name in html_content: is_match = True
                    elif req.product_name and req.product_name in html_content: is_match = True
                    
                    results.append({
                        "rank": current_rank,
                        "title": title_snippet,
                        "storeName": api_data.get("mallName", req.store_name) if is_match and api_data else "",
                        "reviews": reviews,
                        "purchases": purchases,
                        "keeps": keeps,
                        "n1_base": n1_base,
                        "is_target": is_match,
                        "mid": req.target_mid if is_match else f"unknown_{current_rank}",
                        "category": "쇼핑 카테고리",
                        "is_new": "새로오픈" in html_content
                    })
                return results
            
            top_comp = scrape_page(1)
            target_pg = 1
            if api_rank > 0: target_pg = (api_rank - 1) // 40 + 1
            
            t_stats = next((c for c in top_comp if c["is_target"]), None)
            if not t_stats and target_pg > 1:
                target_page_items = scrape_page(target_pg)
                t_stats = next((c for c in target_page_items if c["is_target"]), None)
            
            context.close()
            return top_comp, t_stats

    scrape_blocked = False
    try:
        loop = asyncio.get_running_loop()
        top_competitors, target_stats = await loop.run_in_executor(playwright_executor, scrape_sync)
        # 차단/캡차 감지 시: 테더링 IP 회전 후 1회 재시도
        if blocked_flag["v"]:
            try:
                new_ip = await _shopping_proxy_mgr.rotate_tethering_ip()
                print(f"[shopping] 차단 감지 → 테더링 IP 회전: {new_ip}")
            except Exception as e:
                print(f"[shopping] 테더링 IP 회전 실패: {e}")
            blocked_flag["v"] = False
            top_competitors, target_stats = await loop.run_in_executor(playwright_executor, scrape_sync)
        scrape_blocked = blocked_flag["v"]
    except Exception as e:
         return {"found": False, "message": f"크롤링 에러 발생: {str(e)}"}
         
    if not top_competitors and top_api_items:
        top_competitors = top_api_items
        for t in top_competitors:
            if t["is_target"]:
                target_stats = t
                break

    if not target_stats and api_rank > 0:
        target_stats = {
            "rank": api_rank, "title": api_data.get("title", ""), "storeName": api_data.get("mallName", ""), "price": api_data.get("lprice", 0), "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 80, "is_target": True, "mid": req.target_mid, "category": api_data.get("category", "")
        }
    elif not target_stats:
        # Not found in top 400
        target_stats = {
            "rank": "400위 밖", "title": req.product_name or req.target_mid or req.store_name or "내 상품", "storeName": req.store_name or "", "price": 0, "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 50, "is_target": True, "mid": req.target_mid or "unknown", "category": ""
        }
        
    all_items = list(top_competitors)
    
    # 400위까지 모든 아이템을 결과에 포함시킵니다 (rank 기준 병합)
    items_by_rank = {item.get("rank"): item for item in top_competitors if isinstance(item.get("rank"), int)}
    for api_item in top_api_items:
        r = api_item.get("rank")
        if isinstance(r, int) and r not in items_by_rank:
            items_by_rank[r] = api_item
            
    all_items = sorted(list(items_by_rank.values()), key=lambda x: x.get("rank", 9999))
            
    if target_stats and target_stats.get("mid") not in [i.get("mid") for i in all_items]:
        all_items.append(target_stats)
        
    if not all_items:
        return {"found": False, "message": "데이터가 없습니다."}

    # --- Math Algorithm (Log Scaling & Min-Max Norm) ---
    all_purchases = [log_scale(c['purchases']) for c in all_items]
    all_reviews = [log_scale(c['reviews']) for c in all_items]
    all_keeps = [log_scale(c['keeps']) for c in all_items]
    
    p_max, p_min = max(all_purchases), min(all_purchases)
    r_max, r_min = max(all_reviews), min(all_reviews)
    k_max, k_min = max(all_keeps), min(all_keeps)
    
    for item in all_items:
        p_norm = min_max_norm(log_scale(item['purchases']), p_min, p_max) * 100
        r_norm = min_max_norm(log_scale(item['reviews']), r_min, r_max) * 100
        k_norm = min_max_norm(log_scale(item['keeps']), k_min, k_max) * 100
        
        cvr = p_norm * 0.8
        click = k_norm * 1.2
        if click > 100: click = 100
        
        n1 = item.get('n1_base', 80)
        n2 = 0.5 * p_norm + 0.4 * r_norm + 0.1 * cvr
        n3 = 0.6 * click + 0.4 * k_norm
        n4 = 1.0 # Base penalty filter
        
        s_shop = (0.3 * n1 + 0.7 * (0.7 * n2 + 0.3 * n3)) * n4
        
        item['n1'] = round(n1, 2)
        item['n2'] = round(n2, 2)
        item['n3'] = round(n3, 2)
        item['n4'] = round(n4, 2)
        item['n5'] = round(s_shop, 2) # Total N-Score
        
    # --- Page 1 Sales Analysis ---
    page1_purchases = [c['purchases'] for c in top_competitors]
    avg_sales = sum(page1_purchases) / len(page1_purchases) if page1_purchases else 0
    max_sales = max(page1_purchases) if page1_purchases else 0
    
    page1_stats = {
        "avg_purchases": round(avg_sales),
        "max_purchases": max_sales,
        "avg_reviews": round(sum([c['reviews'] for c in top_competitors]) / len(top_competitors) if top_competitors else 0)
    }

    report = f"""[AI 컨설팅 N지수 정밀 분석 리포트]
1. 1페이지(Top 40) 시장 분석:
  - 1페이지 제품들의 평균 구매수는 {page1_stats['avg_purchases']:,}건, 최대 구매수는 {page1_stats['max_purchases']:,}건으로 집계되었습니다.
  - 최상위 노출을 위해서는 트래픽(N3) 점수 최적화가 필수입니다.

2. 타겟 상품({target_stats['title']}) 진단 결과:
  - 현재 누적 구매수는 {target_stats['purchases']:,}건, 찜수는 {target_stats['keeps']:,}회 입니다.
  - 검색 적합성(N1): {target_stats['n1']}점 / 실거래 인기도(N2): {target_stats['n2']}점 / 유입(N3): {target_stats['n3']}점
  - 최종 융합 스코어(S_shopping): {target_stats['n5']}점
  - 제안: 1페이지 평균치 도달을 위해 리뷰 이벤트 및 외부 유입(N3)을 늘려 전환율(CVR)을 개선하세요.
""" if target_stats else "타겟 상품을 찾지 못했습니다."

    if target_stats:
        increment_quota(current_user["sub"], current_user.get("role", "advertiser"), db)

    return {
        "found": True if target_stats else False,
        "places": all_items,
        "page1_stats": page1_stats,
        "report": report,
        "history": [],
        "scrape_blocked": scrape_blocked,
        "notice": ("⚠️ 네이버 쇼핑이 자동 접속을 일시 제한(차단/보안확인)하여 구매수·리뷰·찜수는 수집하지 못했습니다. "
                   "가격·순위는 공식 API 기준으로 표시됩니다. 잠시 후 다시 시도하거나, USB 테더링으로 IP를 바꿔 재시도하세요.") if scrape_blocked else ""
    }


class AnalyzeExtRequest(BaseModel):
    keyword: str
    target_mid: Optional[str] = ""
    store_name: Optional[str] = ""
    product_name: Optional[str] = ""
    items: List[Dict]

@router.post("/analyze-keyword-ext")
async def analyze_keyword_shopping_ext(req: AnalyzeExtRequest, db: Session = Depends(get_db), current_user: dict = Depends(check_quota)):
    if not (req.store_name or req.product_name or req.target_mid):
        raise HTTPException(status_code=400, detail="타겟 조건 누락")
        
    if req.store_name and req.store_name.isdigit() and len(req.store_name) >= 5:
        req.target_mid = req.store_name
        req.store_name = ""
        
    api_rank, api_data, top_api_items = await fetch_target_rank_via_api(req.keyword, req.store_name, req.product_name, req.target_mid)
    
    top_competitors = req.items

    # 진단: 확장이 보낸 원본 텍스트(html_content)와 파싱값을 로그로 — 실제 형식 확인용
    try:
        _dbg = [0, 1, 2, 5, 7]
        for _i in _dbg:
            if _i < len(top_competitors):
                _it = top_competitors[_i]
                _msg = f"[shopping-ext] item{_i} text={(_it.get('html_content') or '')[:260]!r}"
                print(_msg)
                if logger: logger.error(_msg)
    except Exception:
        pass

    # Process top_competitors to add rank, n1_base, is_target, mid, category, is_new
    results = []
    tokens = req.keyword.split()

    for idx, item in enumerate(top_competitors):
        current_rank = idx + 1
        html_content = item.get("html_content", "")
        href = item.get("href", "") or item.get("link", "")

        # 확장이 보낸 원본 텍스트에서 가격/리뷰/구매/찜/스토어를 정확히 재파싱 (확장 정규식 보정)
        def _num(s):
            s = (s or "").replace(",", "").replace(" ", "")
            try:
                return int(float(s.replace("만", "")) * 10000) if "만" in s else int(float(s))
            except Exception:
                return 0
        # 리뷰수: "리뷰 (539)" 또는 "별점 4.76 (17)"/"★4.76 (17)" (리뷰 글자 없는 형식 모두 대응)
        mm = re.search(r'(?:리뷰|별점\s*[\d.]+|★\s*[\d.]+)\s*\(\s*([\d.,]+\s*만?)\s*\)', html_content)
        if mm: item["reviews"] = _num(mm.group(1))
        mm = re.search(r'구매\s*([\d.,]+\s*만?)', html_content)
        if mm: item["purchases"] = _num(mm.group(1))
        mm = re.search(r'찜(?!하기)\s*([\d.,]+\s*만?)', html_content)
        if mm: item["keeps"] = _num(mm.group(1))
        # 가격비교(카탈로그)면 최저가 + 가격비교 표시, 아니면 판매가
        is_compare = bool(re.search(r'판매처\s*\d', html_content)) or ('쇼핑몰별 최저가' in html_content)
        item["is_compare"] = is_compare
        if is_compare:
            pm = re.search(r'최저\s*([\d,]{2,})\s*원', html_content) or re.search(r'([\d,]{3,})\s*원', html_content)
        else:
            pm = re.search(r'([\d,]{2,})\s*원', html_content)
        if pm: item["price"] = _num(pm.group(1))
        # 등록일 (예: "등록일 2025.04.")
        mm = re.search(r'등록일\s*([0-9]{4}\.\s?[0-9]{1,2}\.?)', html_content)
        if mm: item["reg_date"] = mm.group(1).strip()
        # 스토어명: ①"톡톡 \t {store}정보" ②일반 "{store}정보"(블랙리스트 제외) ③"{store} 정보 상품만 보기"
        _store_bl = ("상품", "구매", "배송", "판매", "상세", "기본", "추가", "제품", "리뷰", "카드",
                     "할인", "이벤트", "혜택", "적립", "포인트", "무이자", "안내", "공지", "수정", "신고", "최저")
        store_txt = ""
        mm = re.search(r'톡톡\s*\t?\s*([가-힣A-Za-z0-9&.\-]{2,20}?)정보', html_content)
        if mm:
            store_txt = mm.group(1)
        else:
            for cm in re.finditer(r'([가-힣A-Za-z0-9][가-힣A-Za-z0-9&.\- ]{1,18}?)\s*정보(?:\s*상품만|\s|$)', html_content):
                cand = cm.group(1).strip()
                if cand and not any(b in cand for b in _store_bl):
                    store_txt = cand
                    break
        if store_txt:
            item["storeName"] = store_txt
        elif is_compare:
            item["storeName"] = "가격비교"

        match_count = sum(1 for t in tokens if t in html_content)
        n1_base = int((match_count / len(tokens)) * 100) if tokens else 0

        def _norm(s):
            return (s or "").replace(" ", "").lower()
        is_match = False
        if req.target_mid and (req.target_mid in html_content or req.target_mid in href):
            is_match = True
        elif req.store_name and (_norm(req.store_name) in _norm(html_content) or _norm(req.store_name) in _norm(store_txt)):
            is_match = True
        elif req.product_name and _norm(req.product_name) in _norm(html_content):
            is_match = True

        item["rank"] = current_rank
        item["n1_base"] = n1_base
        item["is_target"] = is_match
        item["mid"] = req.target_mid if is_match else f"unknown_{current_rank}"
        item["category"] = "쇼핑 카테고리"
        item["is_new"] = "새로오픈" in html_content
        if is_match and api_data:
            item["storeName"] = api_data.get("mallName", req.store_name)
        results.append(item)
        
    top_competitors = results
    
    target_stats = next((c for c in top_competitors if c["is_target"]), None)
    
    if not target_stats and api_rank > 0:
        target_stats = {
            "rank": api_rank, "title": api_data.get("title", ""), "storeName": api_data.get("mallName", ""), "price": int(api_data.get("lprice", 0)) if api_data.get("lprice") else 0, "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 80, "is_target": True, "mid": req.target_mid, "category": api_data.get("category", ""), "is_new": False
        }
    elif not target_stats:
        target_stats = {
            "rank": "400위 밖", "title": req.product_name or req.target_mid or req.store_name or "내 상품", "storeName": req.store_name or "", "price": 0, "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 50, "is_target": True, "mid": req.target_mid or "unknown", "category": "", "is_new": False
        }
        
    all_items = list(top_competitors)
    
    # 400위까지 모든 아이템을 결과에 포함시킵니다 (rank 기준 병합)
    items_by_rank = {item.get("rank"): item for item in top_competitors if isinstance(item.get("rank"), int)}
    for api_item in top_api_items:
        r = api_item.get("rank")
        if isinstance(r, int) and r not in items_by_rank:
            items_by_rank[r] = api_item
            
    all_items = sorted(list(items_by_rank.values()), key=lambda x: x.get("rank", 9999))
            
    if target_stats and target_stats.get("mid") not in [i.get("mid") for i in all_items]:
        all_items.append(target_stats)
        
    if not all_items:
        return {"found": False, "message": "데이터가 없습니다."}

    # --- N지수 스코어링 (개선판) ---
    # 정규화 기준 = 1페이지(Top 40) 실제 항목 (API 0값 더미 제외 → 상위권 변별력 유지)
    from datetime import datetime as _dt
    from collections import Counter as _Counter
    base_items = top_competitors[:40] or all_items
    def _logvals(key):
        return [log_scale(c.get(key, 0) or 0) for c in base_items]
    lp, lr, lk = _logvals('purchases'), _logvals('reviews'), _logvals('keeps')
    p_min, p_max = min(lp), max(lp)
    r_min, r_max = min(lr), max(lr)
    k_min, k_max = min(lk), max(lk)
    _now = _dt.now()
    kw_tokens = [t for t in (req.keyword or '').split() if t]

    def _recency(item):
        m = re.match(r'(\d{4})\.\s?(\d{1,2})', item.get('reg_date') or '')
        if not m:
            return 50.0  # 등록일 미상 → 중립
        months = (_now.year - int(m.group(1))) * 12 + (_now.month - int(m.group(2)))
        return max(0.0, min(100.0, 100.0 - months * 3))  # 0개월=100, 약 33개월=0

    for item in all_items:
        p_norm = min_max_norm(log_scale(item.get('purchases', 0) or 0), p_min, p_max) * 100
        r_norm = min_max_norm(log_scale(item.get('reviews', 0) or 0), r_min, r_max) * 100
        k_norm = min_max_norm(log_scale(item.get('keeps', 0) or 0), k_min, k_max) * 100
        title_str = item.get('title') or ''

        # N1 적합도: 키워드 토큰 일치 + 제목 앞쪽 배치 가중(전진배치 버프)
        n1 = float(item.get('n1_base', 80))
        if kw_tokens and title_str:
            head = title_str[:max(1, len(title_str) // 2)]
            front = sum(1 for t in kw_tokens if t in head) / len(kw_tokens)
            n1 = min(100.0, n1 + front * 15)

        # N2 실거래: 구매 0.6 + 리뷰 0.4
        n2 = 0.6 * p_norm + 0.4 * r_norm

        # N3 트래픽/인기: 찜 인기 0.6 + 최신성 0.4 (+ 신상 보너스)
        n3 = 0.6 * k_norm + 0.4 * _recency(item)
        if item.get('is_new'):
            n3 = min(100.0, n3 + 20)

        # N4 페널티: 제목 길이/특수문자/중복 키워드/스팸 단어
        n4 = 1.0
        if len(title_str) > 50:
            n4 *= 0.7
        if re.search(r'[!@#$%^&*()\[\]{},.~]', title_str):
            n4 *= 0.9
        words = title_str.split()
        if words and max(_Counter(words).values()) >= 3:
            n4 *= 0.9
        if sum(1 for s in SPAM_WORDS if s in title_str) >= 2:
            n4 *= 0.9
        n4 = max(0.5, n4)

        # 총점: 실거래(N2) 50% 중심 + 적합도 25% + 인기/최신성 25%, 페널티 곱
        s_shop = (0.25 * n1 + 0.50 * n2 + 0.25 * n3) * n4

        item['n1'] = round(n1, 2)
        item['n2'] = round(n2, 2)
        item['n3'] = round(n3, 2)
        item['n4'] = round(n4, 2)
        item['n5'] = round(s_shop, 2)

    page1_purchases = [c.get('purchases', 0) for c in top_competitors]
    avg_sales = sum(page1_purchases) / len(page1_purchases) if page1_purchases else 0
    max_sales = max(page1_purchases) if page1_purchases else 0
    
    page1_stats = {
        "avg_purchases": round(avg_sales),
        "max_purchases": max_sales,
        "avg_reviews": round(sum([c.get('reviews', 0) for c in top_competitors]) / len(top_competitors) if top_competitors else 0)
    }

    report = f"""[네이버 쇼핑 N지수 타겟 가이드 리포트]
1. 1페이지(Top 40) 커트라인 분석:
  - 1페이지 제품들의 평균 구매수는 {page1_stats['avg_purchases']:,}건, 평균 리뷰수는 {page1_stats['avg_reviews']:,}건 입니다.
  - 최상위권 진입을 위해서는 구매·리뷰 실거래(N2)가 가장 큰 비중(50%)을 차지합니다. (적합도 25% / 인기·최신성 25%, 패널티 곱)

2. 내 상품({target_stats.get('title', '')}) 진단 결과:
  - 현재 순위: {target_stats.get('rank', '측정불가')}
  - 현재 누적 구매수는 {target_stats.get('purchases', 0):,}건, 리뷰는 {target_stats.get('reviews', 0):,}건 입니다.
  - 검색 적합성(N1): {target_stats.get('n1', 0)}점 / 실거래(N2): {target_stats.get('n2', 0)}점 / 인기·최신성(N3): {target_stats.get('n3', 0)}점 / 패널티(N4): {target_stats.get('n4', 1.0)} (1.0 만점)
  - 최종 랭킹 역산 점수(S_total): {target_stats.get('n5', 0)}점
  - 액션 가이드: { '상품명이 50자를 초과하여 N4 패널티(-30%)를 받고 있습니다. 50자 이내로 즉시 수정하세요.' if target_stats.get('n4', 1.0) < 1.0 else '적합도(N1) 형태소 배열이 안전합니다. 리뷰 이벤트를 통해 구매수(N2)를 1페이지 평균까지 끌어올리는 데 집중하세요.' }
""" if target_stats else "타겟 상품을 찾지 못했습니다."

    if target_stats:
        increment_quota(current_user["sub"], current_user.get("role", "advertiser"), db)

    return {
        "found": True if target_stats else False,
        "places": all_items,
        "page1_stats": page1_stats,
        "report": report,
        "history": []
    }

class TrackRequest(BaseModel):
    mid: str
    keyword: str
    name: str
    places: Optional[List[Dict[Any, Any]]] = None
    report: Optional[str] = None
    target_stats: Optional[Dict[Any, Any]] = None

class BatchTrackRequest(BaseModel):
    items: List[TrackRequest]


@router.post("/track")
async def track_shopping_item(req: TrackRequest, db: Session = Depends(get_db)):
    existing = db.query(ShoppingTrackedItem).filter(ShoppingTrackedItem.mid == req.mid, ShoppingTrackedItem.keyword == req.keyword).first()
    
    places_json = json.dumps(req.places) if req.places else None
    
    if existing:
        return {"success": False, "error": "이미 즐겨찾기에 추가된 항목입니다."}
        
    new_item = ShoppingTrackedItem(
        mid=req.mid, keyword=req.keyword, name=req.name, 
        latest_places=places_json, latest_report=req.report
    )
    db.add(new_item)
    db.commit()
    
    if req.target_stats:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Safely parse rank which might be a string like "400위 밖"
        raw_rank = req.target_stats.get("rank", 0)
        rank_val = 0
        try:
            rank_val = int(raw_rank)
        except (ValueError, TypeError):
            rank_val = 0
            
        hist = ShoppingHistory(
            tracked_id=new_item.id,
            date_str=today_str,
            rank=rank_val,
            page=(rank_val - 1) // 40 + 1 if rank_val > 0 else 1,
            visitor_reviews=req.target_stats.get("reviews", 0),
            saves=req.target_stats.get("keeps", 0),
            purchases=req.target_stats.get("purchases", 0),
            n1=req.target_stats.get("n1", 0),
            n2=req.target_stats.get("n2", 0),
            n3=req.target_stats.get("n3", 0),
            n4=req.target_stats.get("n4", 100),
            n5=req.target_stats.get("n5", 0)
        )
        db.add(hist)
        db.commit()
        
    return {"success": True, "message": "성공적으로 저장되었습니다."}

@router.post("/track/batch")
async def track_shopping_batch(req: BatchTrackRequest, db: Session = Depends(get_db)):
    today_str = datetime.now().strftime("%Y-%m-%d")
    updated_count = 0
    
    try:
        for item_req in req.items:
            try:
                # 세이브포인트 적용: 각 아이템 처리가 독립적으로 롤백될 수 있도록 처리
                with db.begin_nested():
                    existing = db.query(ShoppingTrackedItem).filter(ShoppingTrackedItem.mid == item_req.mid, ShoppingTrackedItem.keyword == item_req.keyword).first()
                    
                    # Create item if it doesn't exist
                    if not existing:
                        places_json = json.dumps(item_req.places) if item_req.places else None
                        existing = ShoppingTrackedItem(
                            mid=item_req.mid, keyword=item_req.keyword, name=item_req.name, 
                            latest_places=places_json, latest_report=item_req.report
                        )
                        db.add(existing)
                        db.flush() # commit 대신 flush를 사용하여 트랜잭션 유지
                        
                    if item_req.target_stats:
                        # Check if history for today already exists
                        hist = db.query(ShoppingHistory).filter(
                            ShoppingHistory.tracked_id == existing.id, 
                            ShoppingHistory.date_str == today_str
                        ).first()
                        
                        raw_rank = item_req.target_stats.get("rank", 0)
                        rank_val = 0
                        try:
                            rank_val = int(raw_rank)
                        except (ValueError, TypeError):
                            rank_val = 0
                            
                        if hist:
                            # Update today's history
                            hist.rank = rank_val
                            hist.page = (rank_val - 1) // 40 + 1 if rank_val > 0 else 1
                            hist.visitor_reviews = item_req.target_stats.get("reviews", 0)
                            hist.saves = item_req.target_stats.get("keeps", 0)
                            hist.purchases = item_req.target_stats.get("purchases", 0)
                            hist.price = item_req.target_stats.get("price", 0)
                            hist.n1 = item_req.target_stats.get("n1", 0)
                            hist.n2 = item_req.target_stats.get("n2", 0)
                            hist.n3 = item_req.target_stats.get("n3", 0)
                            hist.n4 = item_req.target_stats.get("n4", 100)
                            hist.n5 = item_req.target_stats.get("n5", 0)
                        else:
                            # Create new history
                            hist = ShoppingHistory(
                                tracked_id=existing.id,
                                date_str=today_str,
                                rank=rank_val,
                                page=(rank_val - 1) // 40 + 1 if rank_val > 0 else 1,
                                visitor_reviews=item_req.target_stats.get("reviews", 0),
                                saves=item_req.target_stats.get("keeps", 0),
                                purchases=item_req.target_stats.get("purchases", 0),
                                price=item_req.target_stats.get("price", 0),
                                n1=item_req.target_stats.get("n1", 0),
                                n2=item_req.target_stats.get("n2", 0),
                                n3=item_req.target_stats.get("n3", 0),
                                n4=item_req.target_stats.get("n4", 100),
                                n5=item_req.target_stats.get("n5", 0)
                            )
                            db.add(hist)
                        updated_count += 1
            except Exception as item_e:
                # db.begin_nested()가 자동으로 세이브포인트 롤백 수행
                pass
                
        db.commit()
        return {"success": True, "message": f"{updated_count}개의 상품 정보가 업데이트되었습니다."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracked")
async def get_tracked_shopping(db: Session = Depends(get_db)):
    items = db.query(ShoppingTrackedItem).order_by(ShoppingTrackedItem.created_at.desc()).all()
    results = []
    
    today_date = datetime.now()
    today_str = today_date.strftime("%Y-%m-%d")
    yesterday_str = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
    last_week_str = (today_date - timedelta(days=7)).strftime("%Y-%m-%d")
    
    for item in items:
        histories = db.query(ShoppingHistory).filter(ShoppingHistory.tracked_id == item.id).order_by(ShoppingHistory.date_str.desc()).all()
        
        current_purchases = 0
        yesterday_purchases = 0
        last_week_purchases = 0
        
        hist_today = None
        hist_yesterday = None
        hist_last_week = None
        
        # Find exact matches or closest previous dates if we don't have exact matches
        for h in histories:
            if h.date_str == today_str:
                hist_today = h
            elif h.date_str == yesterday_str:
                hist_yesterday = h
            elif h.date_str == last_week_str:
                hist_last_week = h
                
        # Fallbacks for sparse data
        if histories:
            if not hist_today:
                hist_today = histories[0] # Most recent available
                
            current_purchases = hist_today.purchases
            
            # Find yesterday or closest before today
            if not hist_yesterday:
                for h in histories:
                    if h.date_str < hist_today.date_str:
                        hist_yesterday = h
                        break
                        
            # Find last week or closest before last week
            if not hist_last_week:
                for h in histories:
                    if h.date_str <= last_week_str:
                        hist_last_week = h
                        break
            
            if hist_yesterday:
                yesterday_purchases = hist_yesterday.purchases
            if hist_last_week:
                last_week_purchases = hist_last_week.purchases
                
        daily_delta = current_purchases - yesterday_purchases if yesterday_purchases > 0 else 0
        weekly_delta = current_purchases - last_week_purchases if last_week_purchases > 0 else 0
        
        results.append({
            "mid": item.mid,
            "keyword": item.keyword,
            "name": item.name,
            "current_purchases": current_purchases,
            "daily_delta": daily_delta,
            "weekly_delta": weekly_delta,
            "last_updated": hist_today.date_str if hist_today else None
        })
        
    return {"success": True, "tracked": results}

@router.post("/history")
async def get_shopping_history(req: AnalyzeRequest, db: Session = Depends(get_db)):
    item = db.query(ShoppingTrackedItem).filter(ShoppingTrackedItem.mid == req.target_mid, ShoppingTrackedItem.keyword == req.keyword).first()
    if not item:
        return {"success": False, "history": []}
    histories = db.query(ShoppingHistory).filter(ShoppingHistory.tracked_id == item.id).order_by(ShoppingHistory.date_str.desc()).limit(30).all()
    
    places = []
    if getattr(item, "latest_places", None):
        try:
            places = json.loads(item.latest_places)
        except:
            pass
            
    return {
        "success": True,
        "history": [
            {
                "date": h.date_str,
                "rank": h.rank,
                "page": h.page,
                "visitor_reviews": h.visitor_reviews,
                "saves": h.saves,
                "purchases": h.purchases,
                "n1": h.n1,
                "n2": h.n2,
                "n3": h.n3,
                "n4": h.n4,
                "n5": h.n5
            } for h in histories
        ],
        "places": places,
        "report": getattr(item, "latest_report", None)
    }

class DeleteTrackedRequest(BaseModel):
    mid: str
    keyword: str

@router.post("/tracked/delete")
async def delete_tracked_shopping(req: DeleteTrackedRequest, db: Session = Depends(get_db)):
    item = db.query(ShoppingTrackedItem).filter(ShoppingTrackedItem.mid == req.mid, ShoppingTrackedItem.keyword == req.keyword).first()
    if not item:
        raise HTTPException(status_code=404, detail="관심상품을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "삭제되었습니다."}


# ══════════════════════════════════════════════════════════════
# 네이버 쇼핑 검색→상품 클릭 유입 부스트 (프록시/테더링 IP 회전)
#  ⚠️ '유입 보조' 도구 — 순위 보장 아님. 비정상 클릭은 어뷰징 감지·페널티 위험.
# ══════════════════════════════════════════════════════════════
import uuid as _uuid_boost
shopping_boost_tasks = {}

def _shopping_click_sync(keyword: str, store_name: str, mid: str, proxy_config):
    """검색 후 내 상품(스토어명/MID)을 찾아 클릭하고 체류. (found, clicked, blocked, rank) 반환."""
    import urllib.parse, random
    out = {"found": False, "clicked": False, "blocked": False, "rank": 0}
    with sync_playwright() as p:
        profile_dir = _get_profile_dir("shopping_boost")
        opts = dict(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--window-size=1920,1080'],
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        if proxy_config:
            opts["proxy"] = proxy_config
        ctx = p.chromium.launch_persistent_context(profile_dir, **opts)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            try:
                stealth(page)
            except Exception:
                pass
            sn = (store_name or "").replace(" ", "")
            for pg in range(1, 6):  # 최대 5페이지(약 200위)까지 탐색
                url = f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(keyword)}&pagingIndex={pg}&pagingSize=40"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000 + random.randint(0, 1500))
                body = page.inner_text("body")[:400]
                if any(k in body for k in SHOPPING_BLOCK_KEYWORDS):
                    out["blocked"] = True
                    break
                for _ in range(3):  # 사람처럼 스크롤
                    page.evaluate("window.scrollBy(0, 1200)")
                    page.wait_for_timeout(450 + random.randint(0, 400))
                items = page.query_selector_all(
                    "[class*='product_item'], [class*='basicList_item'], [class*='adProduct'], [class*='basicProductCard'], li[data-shp-page-key]"
                )
                for idx, it in enumerate(items):
                    try:
                        txt = it.inner_text()
                    except Exception:
                        txt = ""
                    a = it.query_selector("a[href]")
                    href = (a.get_attribute("href") if a else "") or ""
                    matched = (mid and mid in (href + txt)) or (sn and sn in txt.replace(" ", ""))
                    if matched:
                        out["found"] = True
                        out["rank"] = (pg - 1) * 40 + idx + 1
                        link = a or it.query_selector("a")
                        if link:
                            try:
                                link.scroll_into_view_if_needed()
                                page.wait_for_timeout(600)
                                link.click()
                                out["clicked"] = True
                                page.wait_for_timeout(3000 + random.randint(0, 3500))  # 체류
                                prod = ctx.pages[-1]  # 새 탭이면 그쪽
                                try:
                                    prod.evaluate("window.scrollBy(0, 1600)")
                                    prod.wait_for_timeout(1500 + random.randint(0, 1500))
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        break
                if out["found"] or out["blocked"]:
                    break
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return out


async def _shopping_boost_worker(task_id, keyword, store_name, mid, clicks, interval_min, use_tethering):
    st = shopping_boost_tasks[task_id]
    loop = asyncio.get_running_loop()
    for i in range(clicks):
        if st.get("cancel"):
            st["logs"].append("⏹️ 사용자에 의해 중단되었습니다.")
            break
        if use_tethering:
            try:
                ip = await _shopping_proxy_mgr.rotate_tethering_ip()
                st["logs"].append(f"📱 IP 회전: {ip}")
            except Exception as e:
                st["logs"].append(f"⚠️ IP 회전 실패(계속): {e}")
        pc = _shopping_proxy_config()
        try:
            r = await loop.run_in_executor(playwright_executor, lambda: _shopping_click_sync(keyword, store_name, mid, pc))
        except Exception as e:
            r = {"error": str(e)}
        if r.get("error"):
            st["logs"].append(f"[{i+1}/{clicks}] 오류: {r['error'][:120]}")
        elif r.get("blocked"):
            st["logs"].append(f"[{i+1}/{clicks}] ⚠️ 네이버 접속 제한(차단) — 건너뜀 (테더링/프록시 IP 변경 권장)")
        elif r.get("clicked"):
            st["logs"].append(f"[{i+1}/{clicks}] ✅ {r.get('rank')}위 상품 클릭·체류 완료")
        elif r.get("found"):
            st["logs"].append(f"[{i+1}/{clicks}] 상품 찾음(클릭 실패) — {r.get('rank')}위")
        else:
            st["logs"].append(f"[{i+1}/{clicks}] 상품 못 찾음(상위 200위 밖이거나 키워드 불일치)")
        if i < clicks - 1 and interval_min > 0 and not st.get("cancel"):
            st["logs"].append(f"⏳ 다음 유입까지 {interval_min}분 대기...")
            await asyncio.sleep(interval_min * 60)
    if st.get("status") == "running":
        st["status"] = "completed"
        st["logs"].append("🏁 유입 작업 완료")


class ShoppingBoostReq(BaseModel):
    keyword: str
    store_name: Optional[str] = ""
    target_mid: Optional[str] = ""
    clicks: Optional[int] = 5
    interval_min: Optional[int] = 10
    use_tethering: Optional[bool] = False

@router.post("/boost", summary="검색→내 상품 클릭 유입(부스트) 시작")
async def start_shopping_boost(req: ShoppingBoostReq, current_user: dict = Depends(check_quota)):
    if not req.keyword or not (req.store_name or req.target_mid):
        raise HTTPException(status_code=400, detail="검색 키워드와 스토어명(또는 MID)을 입력하세요.")
    tid = _uuid_boost.uuid4().hex
    shopping_boost_tasks[tid] = {"status": "running", "logs": ["🚀 검색→상품 클릭 유입 작업을 시작합니다."], "cancel": False}
    asyncio.create_task(_shopping_boost_worker(
        tid, req.keyword, req.store_name or "", req.target_mid or "",
        max(1, int(req.clicks or 1)), max(0, int(req.interval_min or 0)), bool(req.use_tethering),
    ))
    return {"success": True, "task_id": tid}

@router.get("/boost/status/{task_id}")
async def shopping_boost_status(task_id: str):
    t = shopping_boost_tasks.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return {"status": t["status"], "logs": t["logs"][-100:]}

@router.post("/boost/cancel/{task_id}")
async def shopping_boost_cancel(task_id: str):
    t = shopping_boost_tasks.get(task_id)
    if t:
        t["cancel"] = True
        t["status"] = "failed"
    return {"success": True}


def persist_shopping_history(db, user_id: str, payload: dict, result: dict):
    """[방법 B·DB동기화] 에이전트 shopping_analyze 결과 → ShoppingHistory(일자별)에 기록.
    cloud: jobs.PERSISTERS 훅으로 complete_job 에서 자동 호출 (commit 은 호출측 수행)."""
    import json as _json
    from datetime import datetime as _dt
    from mbam_nextgen.backend.database import ShoppingTrackedItem, ShoppingHistory
    if not isinstance(result, dict) or not result.get("found"):
        return
    places = result.get("places") or []
    target = next((p for p in places if p.get("is_target")), None)
    if not target:
        return

    item = None
    tracked_id = (payload or {}).get("tracked_id")
    if tracked_id:
        item = db.query(ShoppingTrackedItem).filter(ShoppingTrackedItem.id == tracked_id).first()
    if not item:
        item = (db.query(ShoppingTrackedItem)
                .filter(ShoppingTrackedItem.mid == str((payload or {}).get("target_mid") or ""),
                        ShoppingTrackedItem.keyword == ((payload or {}).get("keyword") or ""))
                .first())
    if not item:
        return

    rank = target.get("rank", 0)
    rank = rank if isinstance(rank, int) else 0   # "400위 밖" 등 문자열 → 0
    date_str = _dt.now().strftime("%Y-%m-%d")
    hist = (db.query(ShoppingHistory)
            .filter(ShoppingHistory.tracked_id == item.id, ShoppingHistory.date_str == date_str)
            .first())
    if not hist:
        hist = ShoppingHistory(tracked_id=item.id, date_str=date_str)
        db.add(hist)
    hist.rank = rank
    hist.page = (rank - 1) // 40 + 1 if rank > 0 else 1
    hist.saves = target.get("keeps", 0)
    hist.visitor_reviews = target.get("reviews", 0)
    hist.purchases = target.get("purchases", 0)
    hist.n1 = target.get("n1", 0)
    hist.n2 = target.get("n2", 0)
    hist.n3 = target.get("n3", 0)
    hist.n4 = target.get("n4", 0)
    hist.n5 = target.get("n5", 0)
    # 목록 화면의 최신 스냅샷/리포트도 함께 갱신
    try:
        item.latest_places = _json.dumps(places, ensure_ascii=False)
        if result.get("report"):
            item.latest_report = result["report"]
    except Exception:
        pass


# 클라우드 모드: 에이전트가 shopping_analyze 결과를 반환하면 자동으로 Postgres에 영속화
try:
    from mbam_nextgen.backend import jobs as _jobs
    _jobs.register_persister("shopping_analyze", persist_shopping_history)
except Exception:
    pass
