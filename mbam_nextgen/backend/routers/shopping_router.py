from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
import asyncio
import httpx
import re
from typing import List, Optional, Dict
import math

try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
except ImportError:
    kiwi = None

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

# ==========================================
# 1. 유틸리티 (형태소 분석 및 정제)
# ==========================================

SPAM_WORDS = {'특가', '무료배송', '이벤트', '신상', '쿠폰', '할인', '정품', '사은품', '당일발송'}

def clean_and_tokenize(keyword: str) -> List[str]:
    """형태소 분리 및 필터링"""
    cleaned = re.sub(r'[!?,\[\]\(\)\{\}\<\>~*]', ' ', keyword)
    if not kiwi:
        return [w for w in cleaned.split() if w not in SPAM_WORDS]
    
    tokens = kiwi.tokenize(cleaned)
    valid_tokens = []
    for t in tokens:
        if t.tag.startswith('N') or t.tag == 'SL':
            word = t.form
            if word not in SPAM_WORDS and not re.fullmatch(r'\d{4}', word):
                valid_tokens.append(word)
    return valid_tokens

def remove_duplicates_keep_order(tokens: List[str]) -> List[str]:
    seen = set()
    return [x for x in tokens if not (x in seen or seen.add(x))]

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

@router.post("/keyword/assemble")
async def assemble_title(req: TitleAssembleRequest):
    """
    50자 이내 SEO 최적화 상품명 조립
    """
    title = ""
    if req.brand_name:
        title += f"{req.brand_name} "
        
    seed = req.seed_keyword.strip()
    if seed:
        title += f"{seed} "
        
    used_words = set(clean_and_tokenize(title))
    
    for token in req.tokens:
        if token not in used_words:
            if len(title) + len(token) + 1 <= 50:
                title += f"{token} "
                used_words.add(token)
            else:
                break
                
    title = title.strip()
    
    return {
        "assembled_title": title,
        "length": len(title),
        "warning": "길이가 50자를 초과할 경우 네이버 검색 알고리즘에서 감점(-30점) 될 수 있습니다." if len(title) > 50 else None
    }

# ==========================================
# 4. 쇼핑 순위 딥 서치 & 스코어 산출 (랭킹 모듈 - Ultimate Hybrid)
# ==========================================
from dotenv import load_dotenv
import os
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import concurrent.futures
from mbam_nextgen.backend.database import get_db, ShoppingTrackedItem, ShoppingHistory
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, APIRouter, Query
from pydantic import BaseModel
import math
import re
import httpx
from datetime import datetime
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
    if not client_id or not client_secret: return 0, None
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    
    target_item = None
    target_rank = 0
    top_api_items = []
    
    async with httpx.AsyncClient() as client:
        for start in [1, 101, 201, 301]:
            url = f"https://openapi.naver.com/v1/search/shop.json?query={keyword}&display=100&start={start}"
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
                    
                    if start == 1 and idx < 40:
                        clean_title = item.get("title", "").replace("<b>","").replace("</b>","")
                        top_api_items.append({
                            "rank": global_rank,
                            "title": clean_title,
                            "storeName": item.get("mallName", ""),
                            "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 0,
                            "is_target": is_match,
                            "mid": item.get("productId", ""),
                            "category": f"{item.get('category1', '')}",
                            "is_new": False
                        })

                if target_rank > 0 and start > 1:
                    break
            except Exception:
                pass
    return target_rank, target_item, top_api_items

@router.post("/analyze-keyword")
async def analyze_keyword_shopping(req: AnalyzeRequest, db: Session = Depends(get_db)):
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
                url = f"https://search.shopping.naver.com/search/all?query={req.keyword}&pagingIndex={pg_num}&pagingSize=40"
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                items = page.query_selector_all("[class^='product_item__'], [class^='basicList_item__']")
                
                results = []
                for idx, item in enumerate(items):
                    html_content = item.inner_text()
                    html_content = html_content.replace('\\n', ' ')
                    
                    review_match = re.search(r'리뷰\\s*([0-9,]+)', html_content)
                    purchase_match = re.search(r'구매\\s*([0-9,]+)', html_content)
                    keep_match = re.search(r'찜\\s*([0-9,]+)', html_content)
                    
                    reviews = int(review_match.group(1).replace(',', '')) if review_match else 0
                    purchases = int(purchase_match.group(1).replace(',', '')) if purchase_match else 0
                    keeps = int(keep_match.group(1).replace(',', '')) if keep_match else 0
                    
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
        with concurrent.futures.ThreadPoolExecutor() as pool:
            top_competitors, target_stats = await loop.run_in_executor(pool, scrape_sync)
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
            "rank": api_rank, "title": api_data["title"], "storeName": api_data.get("mallName", ""), "reviews": 0, "purchases": 0, "keeps": 0, "n1_base": 80, "is_target": True, "mid": req.target_mid, "category": api_data.get("category", "")
        }
        
    all_items = list(top_competitors)
    if target_stats and target_stats not in all_items:
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
        hist = ShoppingHistory(
            tracked_id=new_item.id,
            date_str=today_str,
            rank=req.target_stats.get("rank", 0),
            page=(req.target_stats.get("rank", 1) - 1) // 40 + 1 if req.target_stats.get("rank", 0) > 0 else 1,
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

@router.get("/tracked")
async def get_tracked_shopping(db: Session = Depends(get_db)):
    items = db.query(ShoppingTrackedItem).order_by(ShoppingTrackedItem.created_at.desc()).all()
    return {"success": True, "tracked": [{"mid": i.mid, "keyword": i.keyword, "name": i.name} for i in items]}

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
