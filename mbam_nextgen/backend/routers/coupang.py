from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import concurrent.futures
import json
import os
import re
from urllib.parse import urljoin

from mbam_nextgen.backend.database import get_db, CoupangTrackedItem, CoupangHistory
from mbam_nextgen.backend.quota import check_quota, increment_quota

playwright_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

router = APIRouter()

class AnalyzeCoupangRequest(BaseModel):
    keyword: str
    target_mid: str = "" # 상품번호 (productId)
    store_name: str = "" # 쿠팡은 상점명 대신 상품명으로 주로 매칭
    product_name: str = ""
    compare_days: int = 1

def parse_num(val_str):
    if not val_str: return 0
    val_str = val_str.replace(' ', '')
    if '만' in val_str:
        m = re.search(r'([\d,.]+)', val_str)
        if m:
            try:
                return int(float(m.group(1).replace(',', '')) * 10000)
            except (ValueError, TypeError):
                pass
    val = re.sub(r'[^\d]', '', val_str)
    return int(val) if val else 0

def scrape_coupang_sync(keyword: str, target_mid: str, product_name: str):
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    
    results = []
    target_stats = None
    
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
        Stealth().apply_stealth_sync(page)
        
        try:
            import urllib.parse
            url = f"https://www.coupang.com/np/search?q={urllib.parse.quote(keyword)}&channel=user&component=&eventCategory=SRP&trcid=&traid=&sId=&itemSize=36"
            
            # 페이지 로드 후 응답 확인
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 접근 차단(Access Denied) 감지
            if "Access Denied" in page.title() or (response and response.status == 403):
                browser.close()
                return {"error": "쿠팡 서버가 자동화된 접근을 차단했습니다 (Access Denied). 잠시 후 다시 시도해주세요."}
            
            # 스크롤을 끝까지 내려서 모든 아이템 로딩
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            
            items = page.query_selector_all("li.search-product")
            
            for idx, item in enumerate(items):
                current_rank = idx + 1
                
                # HTML 전체 가져오기
                html_content = item.inner_text() or ""
                
                # 상품 아이디 (data-product-id)
                product_id = item.get_attribute("data-product-id") or f"unknown_{current_rank}"
                
                # 제목 추출
                title_el = item.query_selector("div.name")
                title = title_el.inner_text().strip() if title_el else ""
                if not title:
                    title_match = re.search(r'^[^\n]+', html_content)
                    title = title_match.group(0).strip() if title_match else f"쿠팡 상품 {current_rank}"
                
                # 가격 추출
                price_el = item.query_selector("strong.price-value")
                price = parse_num(price_el.inner_text()) if price_el else 0
                
                # 리뷰수 추출
                review_el = item.query_selector("span.rating-total-count")
                reviews = parse_num(review_el.inner_text()) if review_el else 0
                
                # 별점 추출
                rating_el = item.query_selector("em.rating")
                rating = rating_el.inner_text().strip() if rating_el else "0.0"
                
                # 로켓배송 여부
                rocket_el = item.query_selector("img[src*='rocket']")
                is_rocket = 1 if rocket_el else 0
                
                # 타겟 확인
                is_match = False
                if target_mid and target_mid == product_id:
                    is_match = True
                elif product_name and product_name.replace(" ", "").lower() in title.replace(" ", "").lower():
                    is_match = True
                
                parsed_item = {
                    "rank": current_rank,
                    "title": title[:50],
                    "price": price,
                    "reviews": reviews,
                    "rating": rating,
                    "is_rocket": is_rocket,
                    "is_target": is_match,
                    "mid": product_id,
                    "category": "쿠팡검색",
                    "n1": 80,
                    "n5": current_rank # 단순히 순위로
                }
                
                results.append(parsed_item)
                
                if is_match and not target_stats:
                    target_stats = parsed_item
                    
        except Exception as e:
            browser.close()
            return {"error": f"크롤링 중 에러 발생: {str(e)}"}
            
        browser.close()
        
    return {"places": results, "target_stats": target_stats}

@router.post("/analyze")
async def analyze_coupang(req: AnalyzeCoupangRequest, db: Session = Depends(get_db), current_user: dict = Depends(check_quota)):
    if not (req.product_name or req.target_mid):
        raise HTTPException(status_code=400, detail="타겟 조건 누락")
        
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(playwright_executor, scrape_coupang_sync, req.keyword, req.target_mid, req.product_name)
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"크롤링 에러: {str(e)}")
         
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
        
    places = result.get("places", [])
    target_stats = result.get("target_stats")
    
    if not target_stats:
        target_stats = {
            "rank": "페이지 내 없음", 
            "title": req.product_name or "내 상품", 
            "price": 0, 
            "reviews": 0, 
            "rating": "0.0", 
            "is_rocket": 0, 
            "is_target": True, 
            "mid": req.target_mid or "unknown", 
            "category": "",
            "n1": 50,
            "n5": 0
        }
        places.append(target_stats)
        
    avg_price = sum(p["price"] for p in places if p["price"] > 0) / len([p for p in places if p["price"] > 0]) if places else 0
    avg_reviews = sum(p["reviews"] for p in places if p["reviews"] > 0) / len([p for p in places if p["reviews"] > 0]) if places else 0

    page1_stats = {
        "avg_purchases": 0,
        "max_purchases": 0,
        "avg_reviews": round(avg_reviews),
        "avg_price": round(avg_price)
    }
    
    report = f"""[쿠팡 타겟 가이드 리포트]
1. 검색결과 요약:
  - 노출된 제품들의 평균 가격은 {page1_stats['avg_price']:,}원, 평균 리뷰수는 {page1_stats['avg_reviews']:,}건 입니다.
  - 상위 노출에는 로켓배송 여부와 리뷰/평점이 가장 중요합니다.

2. 내 상품 진단 결과:
  - 현재 순위: {target_stats['rank']}
  - 현재 가격은 {target_stats['price']:,}원, 리뷰는 {target_stats['reviews']:,}건 (평점 {target_stats['rating']}) 입니다.
  - 로켓배송: {'적용됨' if target_stats['is_rocket'] else '미적용 (순위에 치명적입니다)'}
"""
    if target_stats["rank"] != "페이지 내 없음":
        increment_quota(current_user["sub"], current_user.get("role", "advertiser"), db)

    return {
        "found": target_stats["rank"] != "페이지 내 없음",
        "places": places,
        "page1_stats": page1_stats,
        "report": report,
        "history": []
    }

class TrackCoupangRequest(BaseModel):
    mid: str
    keyword: str
    name: str
    places: Optional[List[Dict[Any, Any]]] = None
    report: Optional[str] = None
    target_stats: Optional[Dict[Any, Any]] = None

@router.post("/track")
async def track_coupang_item(req: TrackCoupangRequest, db: Session = Depends(get_db)):
    existing = db.query(CoupangTrackedItem).filter(CoupangTrackedItem.item_id == req.mid, CoupangTrackedItem.keyword == req.keyword).first()
    
    places_json = json.dumps(req.places) if req.places else None
    
    if existing:
        return {"success": False, "error": "이미 즐겨찾기에 추가된 항목입니다."}
        
    new_item = CoupangTrackedItem(
        item_id=req.mid, keyword=req.keyword, name=req.name, 
        latest_places=places_json, latest_report=req.report
    )
    db.add(new_item)
    db.commit()
    
    if req.target_stats:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        raw_rank = req.target_stats.get("rank", 0)
        rank_val = 0
        try:
            rank_val = int(raw_rank)
        except:
            rank_val = 0
            
        hist = CoupangHistory(
            tracked_id=new_item.id,
            date_str=today_str,
            rank=rank_val,
            page=1 if rank_val > 0 else 1,
            reviews=req.target_stats.get("reviews", 0),
            rating=req.target_stats.get("rating", "0.0"),
            price=req.target_stats.get("price", 0),
            is_rocket=req.target_stats.get("is_rocket", 0),
            n1=req.target_stats.get("n1", 0),
            n5=req.target_stats.get("n5", 0)
        )
        db.add(hist)
        db.commit()
        
    return {"success": True, "message": "성공적으로 저장되었습니다."}

@router.get("/tracked")
async def get_tracked_coupang(db: Session = Depends(get_db)):
    items = db.query(CoupangTrackedItem).order_by(CoupangTrackedItem.created_at.desc()).all()
    results = []
    
    for item in items:
        # Get latest history
        hist = db.query(CoupangHistory).filter(CoupangHistory.tracked_id == item.id).order_by(CoupangHistory.date_str.desc()).first()
        results.append({
            "mid": item.item_id,
            "keyword": item.keyword,
            "name": item.name,
            "latest_rank": hist.rank if hist else 0,
            "latest_reviews": hist.reviews if hist else 0,
            "last_updated": hist.date_str if hist else None
        })
    return {"success": True, "tracked": results}

@router.post("/history")
async def get_coupang_history(req: AnalyzeCoupangRequest, db: Session = Depends(get_db)):
    item = db.query(CoupangTrackedItem).filter(CoupangTrackedItem.item_id == req.target_mid, CoupangTrackedItem.keyword == req.keyword).first()
    if not item:
        return {"success": False, "history": []}
        
    histories = db.query(CoupangHistory).filter(CoupangHistory.tracked_id == item.id).order_by(CoupangHistory.date_str.desc()).limit(30).all()
    
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
                "reviews": h.reviews,
                "rating": h.rating,
                "price": getattr(h, "price", 0),
                "is_rocket": h.is_rocket,
                "n1": h.n1,
                "n5": h.n5
            } for h in histories
        ],
        "places": places,
        "report": getattr(item, "latest_report", None)
    }

class DeleteTrackedCoupangRequest(BaseModel):
    mid: str
    keyword: str

@router.post("/tracked/delete")
async def delete_tracked_coupang(req: DeleteTrackedCoupangRequest, db: Session = Depends(get_db)):
    item = db.query(CoupangTrackedItem).filter(CoupangTrackedItem.item_id == req.mid, CoupangTrackedItem.keyword == req.keyword).first()
    if not item:
        raise HTTPException(status_code=404, detail="관심상품을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "삭제되었습니다."}
