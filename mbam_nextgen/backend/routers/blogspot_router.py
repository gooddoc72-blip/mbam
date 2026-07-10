import httpx
import os
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from mbam_nextgen.backend.database import get_db, BlogspotAccount, BlogspotPostHistory, BlogspotKeywordTracker, BlogspotSchedule
from mbam_nextgen.backend.auth import get_current_user

router = APIRouter(
    prefix="/api/blogspot",
    tags=["Blogspot Automation"]
)

class AddAccountRequest(BaseModel):
    account_name: str
    blog_id: str
    access_token: str
    refresh_token: str
    client_id: str
    client_secret: str

class AutoPostRequest(BaseModel):
    account_id: str
    keyword: str
    ai_provider: str = "gemini" # "gemini" or "claude"
    generate_image: bool = True
    source_data: Optional[str] = None  # 글감(선택) — 비우면 키워드만으로 작성

@router.get("/accounts")
def get_accounts(db: Session = Depends(get_db)):
    accounts = db.query(BlogspotAccount).all()
    return {"success": True, "accounts": [{"id": a.id, "account_name": a.account_name, "blog_id": a.blog_id} for a in accounts]}

@router.post("/accounts")
def add_account(req: AddAccountRequest, db: Session = Depends(get_db)):
    # Validate token or just save
    new_acc = BlogspotAccount(
        account_name=req.account_name,
        blog_id=req.blog_id,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        client_id=req.client_id,
        client_secret=req.client_secret
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)
    return {"success": True, "message": "Account added", "id": new_acc.id}

@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
    return {"success": True, "message": "Account deleted"}

async def generate_article(keyword: str, provider: str) -> str:
    # 1. 키워드 기반 글감 수집 (여기서는 생략 및 모의 구현)
    # 2. AI 글 작성
    html_content = ""
    prompt = f"당신은 전문 SEO 블로거입니다. '{keyword}'에 대한 흥미롭고 유익한 블로그 글을 작성해주세요. HTML 형식(h2, h3, p, strong 태그 등)으로 작성하고, <body> 태그는 제외하고 내부 태그만 출력하세요."
    
    if provider == "gemini":
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key: return f"<h2>{keyword}</h2><p>Gemini API 키가 설정되지 않았습니다.</p>"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            data = resp.json()
            try: html_content = data['candidates'][0]['content']['parts'][0]['text']
            except: html_content = f"<p>Gemini 에러: {str(data)}</p>"
            
    elif provider == "claude":
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
        if not claude_key: return f"<h2>{keyword}</h2><p>Claude API 키가 설정되지 않았습니다.</p>"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-3-haiku-20240307", "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]}
            )
            data = resp.json()
            try: html_content = data['content'][0]['text']
            except: html_content = f"<p>Claude 에러: {str(data)}</p>"
            
    return html_content.replace("```html", "").replace("```", "")

@router.post("/post")
async def auto_post(req: AutoPostRequest, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == req.account_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Account not found")

    from mbam_nextgen.services.blogspot_service import generate_blogspot_article, publish_to_blogger

    # 1. 관리자 'blogspot' 프롬프트 + 글감으로 HTML 원고 생성 (제목 자동 추출)
    article = await generate_blogspot_article(req.keyword, req.source_data or "", req.ai_provider)
    title, content = article["title"], article["html"]

    # 2. 대표 이미지(선택) — 본문 맨 위에 삽입
    if req.generate_image:
        image_html = f'<div style="text-align:center;"><img src="https://source.unsplash.com/800x400/?{req.keyword}" alt="{req.keyword}"></div><br/>'
        content = image_html + content

    # 3. Blogger API 발행 (토큰 자동 갱신)
    result = await publish_to_blogger(acc, title, content)

    history = BlogspotPostHistory(
        account_id=acc.id, keyword=req.keyword, title=title,
        post_url=result.get("url", ""), status="success" if result.get("success") else "failed",
    )
    db.add(history)
    db.commit()

    if not result.get("success"):
        return {"success": False, "error": result.get("error")}
    return {"success": True, "post_url": result.get("url", "")}

class TrackKeywordRequest(BaseModel):
    account_id: str
    keyword: str

@router.get("/rank")
def get_tracked_keywords(db: Session = Depends(get_db)):
    # Join with BlogspotAccount to get the account name
    results = db.query(BlogspotKeywordTracker, BlogspotAccount.account_name)\
                .join(BlogspotAccount, BlogspotKeywordTracker.account_id == BlogspotAccount.id)\
                .all()
    
    keywords = []
    for k, acc_name in results:
        keywords.append({
            "id": k.id,
            "account_id": k.account_id,
            "account_name": acc_name,
            "keyword": k.keyword,
            "current_rank": k.current_rank,
            "last_checked_at": k.last_checked_at.strftime("%Y-%m-%d %H:%M") if k.last_checked_at else None
        })
        
    return {"success": True, "keywords": keywords}

@router.post("/rank")
def add_tracked_keyword(req: TrackKeywordRequest, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == req.account_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Account not found")
    
    tracker = BlogspotKeywordTracker(
        account_id=req.account_id,
        keyword=req.keyword,
        current_rank=0 # 초기값
    )
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    return {"success": True, "id": tracker.id}


# ===================== 매일 자동발행 예약 (Blogger API · 클라우드 직접 발행) =====================
class BlogspotScheduleCreate(BaseModel):
    account_ids: Optional[list] = None
    account_id: Optional[str] = None
    schedule_time: str                       # "HH:MM"
    content_category: Optional[str] = None
    post_count_per_day: Optional[int] = 1
    ai_provider: Optional[str] = "gemini"


@router.post("/schedules", summary="블로그스팟 매일 자동발행 예약 추가")
def add_blogspot_schedule(req: BlogspotScheduleCreate, db: Session = Depends(get_db),
                          current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    acc_ids = [a for a in (req.account_ids or []) if a] or ([req.account_id] if req.account_id else [])
    if not acc_ids:
        raise HTTPException(status_code=400, detail="발행할 블로그스팟 계정을 1개 이상 선택하세요.")

    # 등록 시각이 예약 시각을 이미 지났으면 오늘은 건너뛰고 내일부터 (catch-up 즉시 발행 방지)
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI
    _now_kst = _dt.now(_ZI("Asia/Seoul"))
    _last_run = _now_kst.strftime("%Y-%m-%d") if (req.schedule_time or "") <= _now_kst.strftime("%H:%M") else None

    created = []
    for aid in acc_ids:
        acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == aid).first()
        if not acc:
            continue
        sch = BlogspotSchedule(
            user_id=user_id, account_id=aid, schedule_time=req.schedule_time,
            content_category=req.content_category, post_count_per_day=req.post_count_per_day or 1,
            ai_provider=req.ai_provider or "gemini", last_run_date=_last_run,
        )
        db.add(sch)
        db.commit()
        db.refresh(sch)
        created.append(sch.id)
    if not created:
        raise HTTPException(status_code=404, detail="등록 가능한 계정을 찾을 수 없습니다.")
    return {"message": f"블로그스팟 매일 발행 예약이 {len(created)}건 등록되었습니다.", "ids": created}


@router.get("/schedules", summary="블로그스팟 매일 발행 예약 목록")
def get_blogspot_schedules(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    rows = db.query(BlogspotSchedule).filter(BlogspotSchedule.user_id == user_id).all()
    result = []
    for s in rows:
        acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == s.account_id).first()
        result.append({
            "id": s.id, "account_id": s.account_id,
            "account_name": acc.account_name if acc else "(삭제됨)",
            "naver_id": acc.account_name if acc else "(삭제됨)",  # 프론트 공용 렌더 호환
            "schedule_time": s.schedule_time, "content_category": s.content_category,
            "post_count_per_day": s.post_count_per_day, "ai_provider": s.ai_provider,
            "generate_card_news": 0, "distribution_mode": "normal",
            "is_active": s.is_active, "last_run_date": s.last_run_date,
            "last_run_url": s.last_run_url, "last_run_title": s.last_run_title,
        })
    return result


@router.delete("/schedules/{schedule_id}", summary="블로그스팟 매일 발행 예약 삭제")
def delete_blogspot_schedule(schedule_id: str, db: Session = Depends(get_db),
                             current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    sch = db.query(BlogspotSchedule).filter(
        BlogspotSchedule.id == schedule_id, BlogspotSchedule.user_id == user_id
    ).first()
    if sch:
        db.delete(sch)
        db.commit()
    return {"message": "예약이 삭제되었습니다."}
