from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel
import asyncio
import httpx
import re
from typing import List, Optional, Dict
import math
import urllib.parse

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

# Utility functions imported from keyword_seo
from mbam_nextgen.services.keyword_seo import analyze_seo_keyword

# ==========================================
# 2. 키워드 분석 (모듈 1, 2)
# ==========================================

class KeywordAnalyzeRequest(BaseModel):
    seed_keyword: str

@router.post("/keyword/analyze")
async def analyze_keyword(req: KeywordAnalyzeRequest):
    """
    연관 키워드 확장 및 NLP 토큰 풀 추출
    """
    seed = req.seed_keyword.strip()
    
    # Mock data for 연관 키워드 추출
    mock_related_keywords = [
        f"{seed} 추천", f"가성비 {seed}", f"예쁜 {seed}", f"사무실 {seed}", 
        f"소형 {seed}", f"2026 신상 {seed} 특가"
    ]
    
    all_tokens = []
    for kw in mock_related_keywords:
        tokens = clean_and_tokenize(kw)
        all_tokens.extend(tokens)
        
    unique_tokens = remove_duplicates_keep_order(all_tokens)
    seed_tokens = clean_and_tokenize(seed)
    
    return {
        "seed_keyword": seed,
        "seed_tokens": seed_tokens,
        "related_keywords_count": len(mock_related_keywords),
        "valid_tokens_pool": unique_tokens,
        "message": "분석 완료"
    }

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
    
    seed = req.seed_keyword.strip()
    brand = req.brand_name.strip() if req.brand_name else ""
    
    client_id = env.get("NAVER_CLIENT_ID", "")
    client_secret = env.get("NAVER_CLIENT_SECRET", "")
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
    ad_customer_id = env.get("NAVER_CUSTOMER_ID", "")
    ad_access_license = env.get("NAVER_ACCESS_LICENSE", "")
    ad_secret_key = env.get("NAVER_SECRET_KEY", "")
    
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
    
    def scrape_sync():
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            stealth(page)
            
            def scrape_page(pg_num):
                url = f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(req.keyword)}&pagingIndex={pg_num}&pagingSize=40"
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                items = page.query_selector_all("[class^='product_item__'], [class^='basicList_item__']")
                
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
            
            browser.close()
            return top_comp, t_stats
            
    try:
        loop = asyncio.get_running_loop()
        top_competitors, target_stats = await loop.run_in_executor(playwright_executor, scrape_sync)
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
        "history": []
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
    
    # Process top_competitors to add rank, n1_base, is_target, mid, category, is_new
    results = []
    tokens = req.keyword.split()
    
    for idx, item in enumerate(top_competitors):
        current_rank = idx + 1
        html_content = item.get("html_content", "")
        
        match_count = sum(1 for t in tokens if t in html_content)
        n1_base = int((match_count / len(tokens)) * 100) if tokens else 0
        
        is_match = False
        if req.target_mid and req.target_mid in html_content: is_match = True
        elif req.store_name and req.store_name in html_content: is_match = True
        elif req.product_name and req.product_name in html_content: is_match = True
        
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

    # --- Math Algorithm (Log Scaling & Min-Max Norm) ---
    all_purchases = [log_scale(c.get('purchases', 0)) for c in all_items]
    all_reviews = [log_scale(c.get('reviews', 0)) for c in all_items]
    all_keeps = [log_scale(c.get('keeps', 0)) for c in all_items]
    
    p_max, p_min = max(all_purchases), min(all_purchases)
    r_max, r_min = max(all_reviews), min(all_reviews)
    k_max, k_min = max(all_keeps), min(all_keeps)
    
    for item in all_items:
        p_norm = min_max_norm(log_scale(item.get('purchases', 0)), p_min, p_max) * 100
        r_norm = min_max_norm(log_scale(item.get('reviews', 0)), r_min, r_max) * 100
        k_norm = min_max_norm(log_scale(item.get('keeps', 0)), k_min, k_max) * 100
        
        n2 = 0.6 * p_norm + 0.3 * r_norm + 0.1 * k_norm
        n3 = 80 if item.get('is_new') else (k_norm * 0.5 + 30)
        n4 = 1.0
        title_str = item.get('title') or ''
        title_len = len(title_str)
        if title_len > 50:
            n4 = 0.7 
        
        n1 = item.get('n1_base', 80)
        s_shop = (0.3 * n1 + 0.7 * (0.8 * n2 + 0.2 * n3)) * n4
        
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
  - 최상위권 진입을 위해서는 구매수(N2)의 실거래 실적이 가장 큰 비중(60%)을 차지합니다.

2. 내 상품({target_stats.get('title', '')}) 진단 결과:
  - 현재 순위: {target_stats.get('rank', '측정불가')}
  - 현재 누적 구매수는 {target_stats.get('purchases', 0):,}건, 리뷰는 {target_stats.get('reviews', 0):,}건 입니다.
  - 검색 적합성(N1): {target_stats.get('n1', 0)}점 / 실거래 인기도(N2): {target_stats.get('n2', 0)}점 / 최신성(N3): {target_stats.get('n3', 0)}점 / 패널티(N4): {target_stats.get('n4', 1.0)} (1.0 만점)
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
